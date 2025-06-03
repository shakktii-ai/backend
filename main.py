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
    safe_print
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
        # Check if files are present in the request
        if 'invoice' not in request.files or 'chart' not in request.files:
            return jsonify({'error': 'Both invoice and chart files are required'}), 400
            
        # Get files from request
        invoice_file = request.files['invoice']
        chart_file = request.files['chart']
        
        # Get sheet name from form data or use default
        sheet_name = request.form.get('sheet_name', 'COA i-Kcal')
        
        # Generate unique ID for this processing job
        unique_id = str(uuid.uuid4())[:8]
        
        # Ensure upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save uploaded files with secure filenames
        invoice_filename = f'invoice_{unique_id}.pdf'
        chart_filename = f'chart_{unique_id}.xlsx'
        
        invoice_path = os.path.join(app.config['UPLOAD_FOLDER'], invoice_filename)
        chart_path = os.path.join(app.config['UPLOAD_FOLDER'], chart_filename)
        
        # Save files
        invoice_file.save(invoice_path)
        chart_file.save(chart_path)
        
        # Process the files using the function from perfect4.py
        result = process_invoice_file(
            invoice_path=invoice_path,
            chart_path=chart_path,
            sheet_name=sheet_name,
            output_dir=app.config['PROCESSED_FOLDER'],
            unique_id=unique_id
        )
        
        # Add download link to the response
        if 'status' in result and result['status'] == 'success':
            result['download_link'] = f'/api/download-file/{os.path.basename(result["output_path"])}'
        
        return jsonify(result)
        
    except Exception as e:
        error_trace = traceback.format_exc()
        safe_print(f"Error in process_invoice: {str(e)}\n{error_trace}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'trace': error_trace
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
            return jsonify({
                'error': "No filename provided. Use /api/download-file/<filename> or /api/download-file?filename=<filename>"
            }), 400
        
        print(f"Attempting to download file: {filename}")
        
        # Ensure the filename is secure
        filename = secure_filename(filename)
        
        # Check if file exists
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({
                'error': f"File not found: {filename}"
            }), 404
            
        return send_from_directory(
            directory=app.config['PROCESSED_FOLDER'],
            path=filename,
            as_attachment=True
        )
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': f"File not found or error downloading: {str(e)}"
        }), 404

# This is needed for running with Gunicorn on Render
application = app

if __name__ == '__main__':
    # Get port from environment variable or use default 10000
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
