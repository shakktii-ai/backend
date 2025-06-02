from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import sys
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
import pandas as pd
import PyPDF2
from flask_cors import CORS
import anthropic
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
        # Check if both files are present in the request
        if 'invoice' not in request.files or 'chart_of_accounts' not in request.files:
            return jsonify({
                'error': 'Both invoice and chart of accounts files are required'
            }), 400
        
        invoice_file = request.files['invoice']
        chart_file = request.files['chart_of_accounts']
        sheet_name = request.form.get('sheet_name', '')  # Optional sheet name
        
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
        # This is where you would integrate your perfect4.py code
        # For now, we'll create a placeholder that just extracts basic PDF info
        
        # Create an output file path
        output_filename = f"{unique_id}_processed_results.xlsx"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Extract text from PDF as a simple placeholder
        with open(invoice_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()
        
        # Read chart of accounts
        if sheet_name and sheet_name != '':
            df = pd.read_excel(chart_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(chart_path)
        
        # Create a simple output DataFrame (this would be replaced with actual processing)
        output_df = pd.DataFrame({
            'Invoice Text Preview': [text[:200]],
            'Chart Rows': [len(df)],
            'Processing Status': ['Placeholder - Replace with actual AI processing']
        })
        
        # Save to Excel
        output_df.to_excel(output_path, index=False)
        
        return output_filename
    except Exception as e:
        print(f"Error in process_files: {str(e)}")
        traceback.print_exc()
        return None

# Route to get Excel sheet names
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
            
        # Save the file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['TEMP_FOLDER'], filename)
        file.save(temp_path)
        
        # Get sheet names
        excel_file = pd.ExcelFile(temp_path)
        sheet_names = excel_file.sheet_names
        
        # Clean up the temporary file
        os.remove(temp_path)
        
        return jsonify({
            'status': 'success',
            'sheet_names': sheet_names
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
