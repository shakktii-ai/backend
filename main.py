from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import sys
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
# Re-enabling pandas for Excel output
import pandas as pd
# import PyPDF2 - still keeping this commented out for now
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
        # Log detailed information about the request for debugging
        print("Received request files:", list(request.files.keys()))
        print("Received form data:", list(request.form.keys()))
        print("Request content type:", request.content_type)
        print("Request data size:", request.content_length)
        
        # Get sheet name from form data
        sheet_name = request.form.get('sheetName', '')
        
        # Check if we have a chart of accounts file
        coa_file_content = request.form.get('coaFile', '')
        invoice_file_content = request.form.get('invoiceFile', '')
        
        # Generate a unique filename for this request
        unique_id = str(uuid.uuid4())[:8]
        result_filename = f"processed_invoice_{unique_id}.xlsx"
        result_path = os.path.join(app.config['PROCESSED_FOLDER'], result_filename)
        
        # Try to load the chart of accounts data if provided as base64 content
        coa_data = None
        if request.files and 'coaFile' in request.files:
            print("Processing uploaded chart of accounts file")
            coa_file = request.files['coaFile']
            if coa_file and coa_file.filename.endswith(('.xlsx', '.xls')):
                # Save the file temporarily
                temp_coa_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_coa_{unique_id}.xlsx")
                coa_file.save(temp_coa_path)
                
                # Try to read the Excel file
                try:
                    # If sheet name is provided, use it, otherwise read the first sheet
                    if sheet_name:
                        coa_data = pd.read_excel(temp_coa_path, sheet_name=sheet_name)
                    else:
                        coa_data = pd.read_excel(temp_coa_path)
                    print(f"Successfully read chart of accounts with {len(coa_data)} rows")
                except Exception as e:
                    print(f"Error reading chart of accounts Excel: {str(e)}")
                    # Still create output but note the error
                    coa_data = pd.DataFrame({"Error": [f"Could not read chart of accounts: {str(e)}"]})  
        
        # Create the output Excel with both request metadata and chart of accounts data if available
        # Create metadata sheet
        metadata = {
            'Timestamp': [datetime.now().isoformat()],
            'Request Content Type': [request.content_type],
            'Received Form Data': [', '.join(list(request.form.keys()))],
            'Invoice File': [invoice_file_content or 'No invoice file provided'],
            'Chart of Accounts File': [coa_file_content or 'No chart of accounts file provided'],
            'Sheet Name': [sheet_name or 'No sheet name provided']
        }
        
        # Create an Excel writer to save multiple sheets
        with pd.ExcelWriter(result_path, engine='openpyxl') as writer:
            # Write the metadata sheet
            metadata_df = pd.DataFrame(metadata)
            metadata_df.to_excel(writer, sheet_name='Request Info', index=False)
            
            # If we have chart of accounts data, write it to another sheet
            if coa_data is not None:
                coa_data.to_excel(writer, sheet_name='Chart of Accounts', index=False)
            
            # Add a sample processed data sheet with some mock invoice data
            # This would be replaced with actual processing logic later
            invoice_data = {
                'Code': ['583', '584', '585', '586', '587', '588', '589'],
                'Name': ['IKE-05-0803-0003', 'IKE-05-0803-0004', 'IKE-05-0804-0000', 'IKE-05-0804-0001', 'IKE-05-0804-0002', 'IKE-05-00-00-0000', 'IKE-06-00-00-0001'],
                'MainGpCode': ['IK', 'IK', 'IK', 'IK', 'IK', 'IK', 'IK'],
                'Primary Group': ['05-', '05-', '05-', '05-', '05-', '06-', '06-'],
                'Main Group': ['Indirect Expenses', 'Indirect Expenses', 'Indirect Expenses', 'Indirect Expenses', 'Indirect Expenses', 'Profit & Loss A/c', 'Profit & Loss A/c'],
                'Sub Group': ['08- Insurance', '08- Insurance', '04- Insurance for Liability', '04- Insurance for Liability', '04- Insurance for Liability', '00-', '00-'],
                'Ledger': ['Property and Plant Insurance', 'Travel Insurance', 'Professional Indemnity', 'Third Party Liability', 'Contractor All Risk Policy', '0002', '0001']
            }
            invoice_df = pd.DataFrame(invoice_data)
            invoice_df.to_excel(writer, sheet_name='Processed Invoice', index=False)
        
        # Return a response format that matches what the frontend expects
        return jsonify({
            'status': 'success',
            'message': 'Invoice and chart of accounts processed successfully',
            'received_form_data': list(request.form.keys()),
            'file_info': {
                'path': result_path,
                'download_url': f'/api/download-file?filename={result_filename}',
                'filename': result_filename,
                'file_type': 'excel'
            }
        })
        
        # Original validation code (commented out for now)
        # if ('invoiceFile' not in request.files and 'invoice' not in request.files) or \
        #    ('coaFile' not in request.files and 'chart_of_accounts' not in request.files):
        #     return jsonify({
        #         'error': 'Both invoice and chart of accounts files are required'
        #     }), 400
        
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

# Route to download processed files - supports both path and query parameters
@app.route('/api/download-file', methods=['GET'])
@app.route('/api/download-file/<path:filename>', methods=['GET'])
def download_file(filename=None):
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
