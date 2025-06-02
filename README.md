# Invoice Processing Backend

This is the Python backend for the invoice processing application. It provides API endpoints for processing invoices against a chart of accounts using Claude AI. The backend directly uses the original Python scripts (`perfect4.py` and `get_excel_sheets.py`) that were previously run locally by the frontend.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   - Create a `.env` file with the following variables:
     ```
     ANTHROPIC_API_KEY=your_claude_api_key
     FLASK_ENV=development
     FLASK_APP=app.main
     ```

3. Run the application:
   ```
   flask run
   ```
   
   For production:
   ```
   gunicorn app.main:app
   ```

## API Endpoints

### Health Check
- `GET /api/health`
  - Returns the current status of the API

### Process Invoice
- `POST /api/process-invoice`
  - Processes an invoice against a chart of accounts
  - Form data:
    - `coaFile`: Excel file with chart of accounts
    - `invoiceFile`: PDF invoice file
    - `sheetName`: (Optional) Name of the sheet in the Excel file
    - `combineInvoices`: (Optional) Boolean to indicate if invoices should be combined
    - `existingFilePath`: (Optional) Path to existing processed file

### Download File
- `GET /api/download-file/{filename}`
  - Downloads a processed file

## Deployment

### Heroku Deployment
1. Create a Heroku account if you don't have one
2. Install Heroku CLI and login
3. Initialize git and commit your files
4. Create a Heroku app: `heroku create your-app-name`
5. Set environment variables: `heroku config:set ANTHROPIC_API_KEY=your_key`
6. Deploy: `git push heroku main`

### Python Anywhere Deployment
1. Create a PythonAnywhere account
2. Upload the files to your PythonAnywhere account
3. Set up a virtual environment and install requirements
4. Configure a WSGI file to point to your Flask app
5. Set environment variables in the PythonAnywhere dashboard
