import os
import sys
import json
import uuid
import re
import shutil
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dynamically add the parent directory to the path to import invoice_processor
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import functions from the original Python files
import perfect4
import get_excel_sheets

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure upload settings
UPLOAD_FOLDER = os.path.join(parent_dir, os.getenv('UPLOAD_FOLDER', 'uploads'))
TEMP_FOLDER = os.path.join(parent_dir, os.getenv('TEMP_FOLDER', 'temp'))
PROCESSED_FOLDER = os.path.join(parent_dir, os.getenv('PROCESSED_FOLDER', 'processed'))

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, TEMP_FOLDER, PROCESSED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Set maximum file size (16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'excel': {'xlsx', 'xls', 'xlsm'},
    'pdf': {'pdf'}
}

def allowed_file(filename, file_type):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(file_type, set())

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint to check if the API is running"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/process-invoice', methods=['POST'])
def upload_and_process():
    """Endpoint for uploading and processing invoice files using perfect4.py directly"""
    try:
        # Check if required files are in the request
        if 'coaFile' not in request.files or 'invoiceFile' not in request.files:
            return jsonify({'error': 'Missing required files'}), 400

        coa_file = request.files['coaFile']
        invoice_file = request.files['invoiceFile']
        
        # Optional parameters
        sheet_name = request.form.get('sheetName', '')
        combine_invoices = request.form.get('combineInvoices', 'false').lower() == 'true'
        existing_file_path = request.form.get('existingFilePath', '')
        
        # Save uploaded files to temp directory
        temp_dir = app.config['UPLOAD_FOLDER']
        os.makedirs(temp_dir, exist_ok=True)
        
        coa_filename = secure_filename(coa_file.filename)
        invoice_filename = secure_filename(invoice_file.filename)
        
        coa_file_path = os.path.join(temp_dir, coa_filename)
        invoice_file_path = os.path.join(temp_dir, invoice_filename)
        
        coa_file.save(coa_file_path)
        invoice_file.save(invoice_file_path)
        
        app.logger.info(f"Files saved: {coa_file_path}, {invoice_file_path}")
        
        # Process the invoice using perfect4.py directly
        # Build the command based on the parameters
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'perfect4.py')
        
        # Prepare command arguments
        cmd = ['python', script_path, coa_file_path, invoice_file_path]
        
        # Add sheet name if provided
        if sheet_name:
            cmd.append(sheet_name)
            
        # Add existing file path if combining invoices
        if combine_invoices and existing_file_path:
            cmd.append(existing_file_path)
            
        app.logger.info(f"Running command: {' '.join(cmd)}")
        
        # Create a temporary file to capture the output
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
        output_file_path = output_file.name
        output_file.close()
        
        # Run the process and capture output
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero return code
        )
        
        # Save stdout to the temp file for debugging
        with open(output_file_path, 'w') as f:
            f.write(process.stdout)
            
        if process.returncode != 0:
            app.logger.error(f"Error running perfect4.py: {process.stderr}")
            return jsonify({'error': f"Script execution failed: {process.stderr}"}), 500
            
        # Try to extract the output file path from the script output
        output_text = process.stdout
        processed_file_path = None
        
        # Look for various patterns that might indicate the output file path
        for line in output_text.splitlines():
            if 'Saved to:' in line or 'saved at:' in line or 'saved to:' in line:
                processed_file_path = line.split(':', 1)[1].strip()
                break
                
        if not processed_file_path:
            # Try to find any path-like string in the output
            import re
            path_match = re.search(r'[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*\.xlsx', output_text)
            if path_match:
                processed_file_path = path_match.group(0)
        
        if not processed_file_path or not os.path.exists(processed_file_path):
            app.logger.error(f"Could not find output file in script output")
            return jsonify({
                'error': 'Could not determine output file path',
                'script_output': output_text
            }), 500
            
        # Move the file to the processed folder for storage
        processed_dir = app.config['PROCESSED_FOLDER']
        os.makedirs(processed_dir, exist_ok=True)
        
        # Generate a unique filename to avoid collisions
        filename = os.path.basename(processed_file_path)
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        stored_file_path = os.path.join(processed_dir, unique_filename)
        
        # Copy the file to the processed directory
        import shutil
        shutil.copy2(processed_file_path, stored_file_path)
        
        # Create download URL
        download_url = f"/api/download-file/{unique_filename}"
        
        return jsonify({
            'success': True,
            'message': 'Invoice processed successfully',
            'script_output': output_text,
            'file_info': {
                'path': stored_file_path,
                'filename': unique_filename,
                'download_url': download_url
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error processing invoice: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-sheets', methods=['POST'])
def get_excel_sheets_endpoint():
    """Endpoint for getting sheets from an Excel file using get_excel_sheets.py"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        if not file or not file.filename or not allowed_file(file.filename, 'excel'):
            return jsonify({"error": "Invalid Excel file"}), 400
        
        # Save the file temporarily
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['TEMP_FOLDER'], filename)
        file.save(file_path)
        
        # Use the get_excel_sheets.py script to get sheet names
        try:
            # We can either use direct import or subprocess
            # Using direct import
            sheets = get_excel_sheets.get_sheets(file_path)
            return jsonify({"success": True, "sheets": sheets})
        except Exception as e:
            app.logger.error(f"Error with direct import: {str(e)}")
            
            # Fallback to subprocess if direct import fails
            try:
                script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'get_excel_sheets.py')
                process = subprocess.run(
                    ['python', script_path, file_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if process.returncode != 0:
                    return jsonify({"error": f"Error getting sheets: {process.stderr}"}), 500
                    
                # Try to parse the output as JSON
                try:
                    result = json.loads(process.stdout)
                    return jsonify({"success": True, "sheets": result})
                except json.JSONDecodeError:
                    # If not JSON, assume it's a list of sheet names separated by newlines
                    sheets = [s.strip() for s in process.stdout.strip().split('\n') if s.strip()]
                    return jsonify({"success": True, "sheets": sheets})
                    
            except Exception as subprocess_error:
                return jsonify({"error": f"Error reading Excel sheets: {str(subprocess_error)}"}), 500
            
    except Exception as e:
        app.logger.error(f"Error getting Excel sheets: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/download-file/<filename>', methods=['GET'])
def download_file(filename):
    """Download a processed file"""
    try:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        return send_file(
            file_path, 
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        app.logger.error(f"Error downloading file: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    # Get port from environment variable or use 5000 as default
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')
