from flask import Flask, jsonify, request, send_from_directory
import os
from datetime import datetime

# Create required folders immediately
for folder in ['uploads', 'temp', 'processed']:
    os.makedirs(folder, exist_ok=True)

# Create the Flask application
app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
