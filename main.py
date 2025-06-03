from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import sys
import traceback
import uuid
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import pandas as pd
import json
from perfect4 import (
    process_invoice_file,
    get_excel_sheets,
    safe_print,
    analyze_excel_structure,
    update_chart_of_accounts
)

# Initialize Flask app and configuration
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load environment variables
load_dotenv()

# Configure file upload settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
PROCESSED_FOLDER = os.environ.get('PROCESSED_FOLDER', os.path.join(BASE_DIR, 'processed'))
TEMP_FOLDER = os.environ.get('TEMP_FOLDER', os.path.join(BASE_DIR, 'temp'))

# Create required directories
for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)
    safe_print(f"Created directory: {folder}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': pd.Timestamp.now().isoformat(),
        'directories': {
            'uploads': app.config['UPLOAD_FOLDER'],
            'processed': app.config['PROCESSED_FOLDER'],
            'temp': app.config['TEMP_FOLDER']
        }
    }), 200

@app.route('/', methods=['GET'])
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice Processing API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            .endpoint {
                background: #f4f4f4;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
            }
            code {
                background: #e4e4e4;
                padding: 2px 5px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <h1>Invoice Processing API</h1>
        <p>Welcome to the Invoice Processing API. Use the following endpoints:</p>
        
        <div class="endpoint">
            <h3>Health Check</h3>
            <p><code>GET /api/health</code> - Check if the API is running</p>
        </div>
        
        <div class="endpoint">
            <h3>Process Invoice</h3>
            <p><code>POST /api/process-invoice</code> - Process an invoice and update chart of accounts</p>
            <p>Parameters (multipart/form-data):</p>
            <ul>
                <li><code>invoice</code> - The invoice PDF file</li>
                <li><code>chart</code> - The chart of accounts Excel file</li>
                <li><code>sheet_name</code> - (Optional) Sheet name in the Excel file (default: 'COA i-Kcal')</li>
            </ul>
        </div>
        
        <div class="endpoint">
            <h3>Get Excel Sheets</h3>
            <p><code>GET /api/get-sheets?file_path=path/to/file.xlsx</code> - List all sheets in an Excel file</p>
        </div>
        
        <div class="endpoint">
            <h3>Download File</h3>
            <p><code>GET /api/download-file/&lt;filename&gt;</code> - Download a processed file</p>
        </div>
    </body>
    </html>
    """


# Route to handle file uploads and process invoices
@app.route('/api/process-invoice', methods=['POST'])
def process_invoice():
    # Initialize variables
    invoice_path = None
    chart_path = None
    
    try:
        # Debug: Log request data
        safe_print("Received request with form data:", request.form)
        safe_print("Received files:", request.files)
        
        # Get files from request
        invoice_file = request.files.get('invoiceFile')
        chart_file = request.files.get('coaFile')
        
        safe_print(f"Invoice file: {invoice_file.filename if invoice_file else 'Not found'}")
        safe_print(f"Chart file: {chart_file.filename if chart_file else 'Not found'}")
        
        # Check if files are present in the request
        if not invoice_file or not chart_file:
            return jsonify({
                'status': 'error', 
                'message': 'Both invoice (PDF) and chart of accounts (Excel) files are required',
                'received_files': {
                    'invoice': bool(invoice_file),
                    'chart': bool(chart_file)
                }
            }), 400
            
        # Validate file types
        if not (invoice_file.filename and invoice_file.filename.lower().endswith('.pdf')):
            return jsonify({
                'status': 'error',
                'message': 'Invoice file must be a PDF',
                'received_file': invoice_file.filename
            }), 400
            
        if not (chart_file.filename and (chart_file.filename.lower().endswith('.xlsx') or 
                                       chart_file.filename.lower().endswith('.xls') or
                                       chart_file.filename.lower().endswith('.xlsm'))):
            return jsonify({
                'status': 'error',
                'message': 'Chart of accounts must be an Excel file (.xlsx, .xls, .xlsm)',
                'received_file': chart_file.filename
            }), 400
            
        # Get sheet name from form data or use default
        sheet_name = request.form.get('sheetName', 'COA i-Kcal')
        safe_print(f"Using sheet name: {sheet_name}")
        
        # Generate unique ID for this processing job
        unique_id = str(uuid.uuid4())[:8]
        safe_print(f"Generated unique ID: {unique_id}")
        
        # Ensure upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save uploaded files with secure filenames
        invoice_filename = f'invoice_{unique_id}.pdf'
        chart_filename = f'chart_{unique_id}.xlsx'
        
        invoice_path = os.path.join(app.config['UPLOAD_FOLDER'], invoice_filename)
        chart_path = os.path.join(app.config['UPLOAD_FOLDER'], chart_filename)
        
        safe_print(f"Saving invoice to: {invoice_path}")
        safe_print(f"Saving chart to: {chart_path}")
        
        # Save files
        invoice_file.save(invoice_path)
        chart_file.save(chart_path)
        
        safe_print("Files saved successfully. Starting processing...")
        
        # Ensure the processed directory exists
        processed_dir = app.config['PROCESSED_FOLDER']
        os.makedirs(processed_dir, exist_ok=True)
        
        # Process the invoice using perfect4 module
        safe_print(f"\n=== Starting invoice processing ===")
        safe_print(f"Current working directory: {os.getcwd()}")
        safe_print(f"Invoice path: {invoice_path} (exists: {os.path.exists(invoice_path)})")
        safe_print(f"Chart path: {chart_path} (exists: {os.path.exists(chart_path)})")
        safe_print(f"Sheet: {sheet_name}")
        safe_print(f"Output dir: {processed_dir} (exists: {os.path.exists(processed_dir)})")
        safe_print(f"Unique ID: {unique_id}")
        
        # List files in the upload directory for debugging
        try:
            upload_files = os.listdir(os.path.dirname(invoice_path))
            safe_print(f"Files in upload directory: {upload_files}")
        except Exception as e:
            safe_print(f"Error listing upload directory: {str(e)}")
        
        # List files in the output directory before processing
        try:
            output_files_before = os.listdir(processed_dir)
            safe_print(f"Files in output directory before processing: {output_files_before}")
        except Exception as e:
            safe_print(f"Error listing output directory: {str(e)}")
        
        safe_print("\nCalling process_invoice_file...")
        result = process_invoice_file(
            invoice_path=invoice_path,
            chart_path=chart_path,
            sheet_name=sheet_name,
            output_dir=processed_dir,
            unique_id=unique_id
        )
        
        # List files in the output directory after processing
        try:
            output_files_after = os.listdir(processed_dir)
            safe_print(f"Files in output directory after processing: {output_files_after}")
            new_files = list(set(output_files_after) - set(output_files_before))
            if new_files:
                safe_print(f"New files created: {new_files}")
            else:
                safe_print("No new files were created")
        except Exception as e:
            safe_print(f"Error listing output directory after processing: {str(e)}")
        
        # Log the result
        safe_print("\n=== Processing Result ===")
        safe_print(f"Status: {result.get('status')}")
        safe_print(f"Message: {result.get('message')}")
        
        # Ensure the output path is using the correct processed directory
        if 'output_path' in result:
            # Make sure the path is using the correct directory
            filename = os.path.basename(result['output_path'])
            result['output_path'] = os.path.join(processed_dir, filename)
            result['output_filename'] = filename
            safe_print(f"Output file: {result['output_path']}")
            
            # Verify the file was created
            if os.path.exists(result['output_path']):
                file_size = os.path.getsize(result['output_path'])
                safe_print(f"File created successfully. Size: {file_size} bytes")
            else:
                safe_print("WARNING: Output file not found after processing")
        
        # Add download link and file info to the response
        if 'status' in result and result['status'] == 'success':
            # Create the response object with the structure expected by the frontend
            response_data = {
                'status': 'success',
                'message': result.get('message', 'Invoice processed successfully'),
                'file_info': {
                    'filename': result.get('output_filename', ''),
                    'path': result.get('output_path', ''),
                    'download_url': f'/api/download-file/{os.path.basename(result["output_path"])}',
                    'file_type': 'excel'
                },
                'invoice_data': result.get('invoice_data', {})
            }
            safe_print("\n=== Processing completed successfully ===\n")
            return jsonify(response_data)
        else:
            # If there was an error, return the error details
            error_msg = result.get('message', 'Failed to process invoice')
            error_trace = result.get('trace', '')
            safe_print(f"\n!!! PROCESSING FAILED: {error_msg}")
            if error_trace:
                safe_print(f"Error details:\n{error_trace}")
                
            return jsonify({
                'status': 'error',
                'error': error_msg,
                'details': error_trace
            }), 500
        
    except Exception as e:
        error_trace = traceback.format_exc()
        error_message = str(e)
        safe_print(f"Error in process_invoice: {error_message}\n{error_trace}")
        return jsonify({
            'status': 'error',
            'error': error_message,
            'message': error_message,  # For backward compatibility
            'details': error_trace,
            'file_info': None
        }), 500
        
    finally:
        # Clean up uploaded files
        for file_path in [invoice_path, chart_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    safe_print(f"Error removing file {file_path}: {str(e)}")

# Route to get sheet names from an Excel file
@app.route('/api/get-sheets', methods=['GET', 'POST'])
def get_excel_sheets():
    try:
        if request.method == 'GET':
            # Handle GET request with file_path parameter
            file_path = request.args.get('file_path')
            if not file_path:
                return jsonify({
                    'status': 'error',
                    'message': 'File path is required as a query parameter: /api/get-sheets?file_path=path/to/file.xlsx'
                }), 400
            
            # Ensure the file exists
            if not os.path.exists(file_path):
                return jsonify({
                    'status': 'error',
                    'message': f'File not found: {file_path}'
                }), 404
            
            # Get sheet names using the function from perfect4.py
            sheet_names = get_excel_sheets(file_path)
            
            return jsonify({
                'status': 'success',
                'file_path': file_path,
                'sheets': sheet_names
            })
            
        elif request.method == 'POST':
            # Handle file upload
            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': 'No file provided'}), 400
                
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'status': 'error', 'message': 'No file selected'}), 400
                
            if not file.filename.endswith(('.xls', '.xlsx')):
                return jsonify({'status': 'error', 'message': 'File must be an Excel file (.xls or .xlsx)'}), 400
            
            # Save the file temporarily
            temp_path = os.path.join(app.config['TEMP_FOLDER'], secure_filename(file.filename))
            file.save(temp_path)
            
            try:
                # Get sheet names using the function from perfect4.py
                sheet_names = get_excel_sheets(temp_path)
                
                return jsonify({
                    'status': 'success',
                    'filename': file.filename,
                    'sheets': sheet_names
                })
            finally:
                # Clean up the temporary file
                try:
                    os.remove(temp_path)
                except Exception as e:
                    safe_print(f"Error removing temporary file: {str(e)}")
    
    except Exception as e:
        error_trace = traceback.format_exc()
        safe_print(f"Error in get_excel_sheets: {str(e)}\n{error_trace}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'trace': error_trace
        }), 500

# Route to download processed files
@app.route('/api/download-file/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        # Check if filename is provided as query parameter (priority)
        query_filename = request.args.get('filename')
        if query_filename:
            filename = query_filename
        
        # If we still don't have a filename, return an error
        if not filename:
            error_msg = "No filename provided. Use /api/download-file/<filename> or /api/download-file?filename=<filename>"
            safe_print(f"Error: {error_msg}")
            return jsonify({
                'status': 'error',
                'error': error_msg
            }), 400
        
        safe_print(f"\n=== Download Request ===")
        safe_print(f"Requested file: {filename}")
        
        # Ensure the filename is secure and doesn't contain path traversal
        filename = secure_filename(os.path.basename(filename))
        safe_print(f"Sanitized filename: {filename}")
        
        # Define the base directory for downloads
        base_dir = app.config['PROCESSED_FOLDER']
        safe_print(f"Base directory: {base_dir}")
        
        # Construct absolute path
        file_path = os.path.abspath(os.path.join(base_dir, filename))
        safe_print(f"Full file path: {file_path}")
        
        # Security check: Ensure the file is within the allowed directory
        abs_base_dir = os.path.abspath(base_dir)
        if not file_path.startswith(abs_base_dir):
            error_msg = f"Security alert: Attempted path traversal: {file_path} (base: {abs_base_dir})"
            safe_print(error_msg)
            return jsonify({
                'status': 'error',
                'error': 'Invalid file path',
                'details': error_msg
            }), 403
        
        # Check if file exists
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            safe_print(error_msg)
            
            # Try to list files in the directory for debugging
            try:
                files = os.listdir(base_dir)
                safe_print(f"\nAvailable files in {base_dir}:")
                for f in files:
                    safe_print(f"- {f} (size: {os.path.getsize(os.path.join(base_dir, f))} bytes)")
            except Exception as e:
                safe_print(f"Error listing directory {base_dir}: {str(e)}")
            
            return jsonify({
                'status': 'error',
                'error': f'File not found: {filename}',
                'available_files': files if 'files' in locals() else [],
                'directory': base_dir
            }), 404
            
        # Get file stats for logging
        file_size = os.path.getsize(file_path)
        safe_print(f"File found. Size: {file_size} bytes")
        
        # Log the download attempt
        safe_print(f"Serving file: {file_path}")
        
        # Send the file
        response = send_from_directory(
            directory=os.path.dirname(file_path),
            path=os.path.basename(file_path),
            as_attachment=True,
            download_name=filename  # This sets the filename in the download dialog
        )
        
        safe_print("File sent successfully")
        return response
        
    except Exception as e:
        error_msg = f"Error downloading file: {str(e)}"
        safe_print(f"\n!!! ERROR: {error_msg}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'error': error_msg,
            'trace': traceback.format_exc()
        }), 500

# This is needed for running with Gunicorn on Render
application = app

if __name__ == '__main__':
    # Get port from environment variable or use default 10000
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
