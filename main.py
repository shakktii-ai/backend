from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import sys
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
# Removing problematic imports for initial deployment
# import pandas as pd
# import PyPDF2
from flask_cors import CORS
# import anthropic
import json
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Create required folders immediately
for folder in ['uploads', 'temp', 'processed']:
    os.makedirs(folder, exist_ok=True)

# Create the Flask application
app = Flask(__name__)

# Enable CORS for all routes and origins
CORS(app)

# Configure file upload settings
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TEMP_FOLDER'] = 'temp'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# In Flask 2.3+, before_first_request is removed
# Instead, we'll create a function that runs with the first request
@app.before_request
def initialize_app():
    # Only run once using an app variable to track initialization
    if not getattr(app, 'initialized', False):
        app.initialized = True
        # Any additional initialization can go here

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "Flask API is running"
    })

@app.route('/', methods=['GET'])
def index():
    return """
    <html>
        <head>
            <title>Invoice Processor API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #333; }
                .endpoint { background: #f4f4f4; padding: 10px; margin: 10px 0; border-radius: 5px; }
                code { background: #e4e4e4; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>Invoice Processor API Documentation</h1>
            <p>This API allows you to process invoices against a chart of accounts using Claude AI.</p>
            
            <h2>API Endpoints</h2>
            
            <div class="endpoint">
                <h3>1. Health Check</h3>
                <code>GET /api/health</code>
                <p>Returns the API status and timestamp.</p>
            </div>
            
            <div class="endpoint">
                <h3>2. Process Invoice</h3>
                <code>POST /api/process-invoice</code>
                <p>Processes an invoice against a chart of accounts.</p>
            </div>
            
            <div class="endpoint">
                <h3>3. Get Excel Sheets</h3>
                <code>POST /api/get-sheets</code>
                <p>Returns the sheet names from an Excel file.</p>
            </div>
            
            <div class="endpoint">
                <h3>4. Download File</h3>
                <code>GET /api/download-file/{filename}</code>
                <p>Downloads a processed file.</p>
            </div>
        </body>
    </html>
    """

# This is what Render.com needs - app must be importable from this file
application = app

# Route to handle file uploads and process invoices
@app.route('/api/process-invoice', methods=['POST'])
def process_invoice():
    try:
        print("Received request files:", list(request.files.keys()))
        print("Received form data:", list(request.form.keys()))
        
        # Check if both files are present in the request
        # Support both the frontend field names (invoiceFile, coaFile) and our backend names
        if ('invoiceFile' not in request.files and 'invoice' not in request.files) or \
           ('coaFile' not in request.files and 'chart_of_accounts' not in request.files):
            return jsonify({
                'error': 'Both invoice and chart of accounts files are required'
            }), 400
        
        # Get files using frontend field names or fallback to backend names
        invoice_file = request.files.get('invoiceFile') or request.files.get('invoice')
        chart_file = request.files.get('coaFile') or request.files.get('chart_of_accounts')
        sheet_name = request.form.get('sheetName', '')  # Optional sheet name - from frontend
        
        # Check if filenames are valid
        if invoice_file.filename == '' or chart_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Secure the filenames
        invoice_filename = secure_filename(invoice_file.filename)
        chart_filename = secure_filename(chart_file.filename)
        
        # Generate unique filenames to prevent overwriting
        unique_id = str(uuid.uuid4())
        invoice_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{invoice_filename}")
        chart_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{chart_filename}")
        
        # Save the uploaded files
        invoice_file.save(invoice_path)
        chart_file.save(chart_path)
        
        # Process the invoice (this would call your perfect4.py logic)
        result_filename = process_files(invoice_path, chart_path, sheet_name, unique_id)
        
        if result_filename:
            return jsonify({
                'status': 'success',
                'message': 'Invoice processed successfully',
                'result_file': result_filename
            })
        else:
            return jsonify({
                'error': 'Failed to process invoice'
            }), 500
            
    except Exception as e:
        print(f"Error processing invoice: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': f"An error occurred: {str(e)}"
        }), 500

# Function to process the files using the perfect4.py logic
def process_files(invoice_path, chart_path, sheet_name, unique_id):
    try:
        # This is a simplified placeholder implementation without pandas and PyPDF2
        # In the future, we'll integrate your perfect4.py code here
        
        # Create an output file path - using .txt instead of .xlsx for simplicity
        output_filename = f"{unique_id}_processed_results.txt"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Just log file information instead of actual processing
        invoice_size = os.path.getsize(invoice_path)
        chart_size = os.path.getsize(chart_path)
        
        # Create a simple text file with the processing info
        with open(output_path, 'w') as f:
            f.write(f"Invoice File: {os.path.basename(invoice_path)}\n")
            f.write(f"Invoice Size: {invoice_size} bytes\n")
            f.write(f"Chart of Accounts: {os.path.basename(chart_path)}\n")
            f.write(f"Chart Size: {chart_size} bytes\n")
            f.write(f"Sheet Name: {sheet_name if sheet_name else 'Default'}\n")
            f.write(f"Processing Timestamp: {datetime.now().isoformat()}\n")
            f.write("Status: Placeholder - Actual processing will be implemented later")
        
        return output_filename
    except Exception as e:
        print(f"Error in process_files: {str(e)}")
        traceback.print_exc()
        return None

# Route to get Excel sheet names - simplified version for initial deployment
@app.route('/api/get-sheets', methods=['POST'])
def get_excel_sheets():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.endswith(('.xls', '.xlsx')):
            return jsonify({'error': 'File must be an Excel file (.xls or .xlsx)'}), 400
            
        # For initial deployment, return dummy sheet names
        # This will be replaced with actual Excel parsing later
        dummy_sheet_names = ['Sheet1', 'Sheet2', 'Data']
        
        return jsonify({
            'status': 'success',
            'message': 'Full Excel parsing will be implemented in a future update',
            'sheet_names': dummy_sheet_names
        })
        
    except Exception as e:
        print(f"Error getting Excel sheets: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': f"An error occurred: {str(e)}"
        }), 500

# Route to download processed files
@app.route('/api/download-file/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(
            directory=app.config['PROCESSED_FOLDER'],
            path=filename,
            as_attachment=True
        )
    except Exception as e:
        return jsonify({
            'error': f"File not found or error downloading: {str(e)}"
        }), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
