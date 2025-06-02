import streamlit as st
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="Invoice Processing API",
    page_icon="📊",
    layout="centered"
)

# Title and introduction
st.title("Invoice Processor API Documentation")
st.write("""
This API allows you to process invoices against a chart of accounts using Claude AI.
The API is implemented using Flask and is accessible at your deployment URL.
""")

# API endpoints documentation
st.header("API Endpoints")

# Health check endpoint
st.subheader("1. Health Check")
st.code("GET /api/health", language="bash")
st.write("Returns the API status and timestamp.")
st.code("""{
  "status": "healthy",
  "timestamp": "2025-06-02T10:30:45.123456"
}""", language="json")

# Process invoice endpoint
st.subheader("2. Process Invoice")
st.code("POST /api/process-invoice", language="bash")
st.write("Processes an invoice against a chart of accounts.")
st.markdown("""
**Request Body (multipart/form-data):**
- `coaFile`: Excel file containing the Chart of Accounts
- `invoiceFile`: PDF file containing the invoice to process
- `sheetName` (optional): Sheet name in the Excel file to use
- `combineInvoices` (optional): Boolean indicating whether to combine invoices
- `existingFilePath` (optional): Path to existing file for combining invoices
""")
st.code("""{
  "success": true,
  "message": "Invoice processed successfully",
  "file_info": {
    "path": "processed/20250602103045_output.xlsx",
    "filename": "20250602103045_output.xlsx",
    "download_url": "/api/download-file/20250602103045_output.xlsx"
  }
}""", language="json")

# Get Excel sheets endpoint
st.subheader("3. Get Excel Sheets")
st.code("POST /api/get-sheets", language="bash")
st.write("Returns the sheet names from an Excel file.")
st.markdown("""
**Request Body (multipart/form-data):**
- `file`: Excel file to get sheets from
""")
st.code("""{
  "success": true,
  "sheets": ["Sheet1", "Sheet2", "Chart of Accounts"]
}""", language="json")

# Download file endpoint
st.subheader("4. Download File")
st.code("GET /api/download-file/{filename}", language="bash")
st.write("Downloads a processed file.")
st.markdown("""
**Path Parameters:**
- `filename`: Name of the file to download
""")

# Environment variables
st.header("Environment Variables")
st.markdown("""
- `ANTHROPIC_API_KEY`: Your Claude API key
- `FLASK_ENV`: Environment mode (development/production)
- `FLASK_APP`: Flask application entry point
- `UPLOAD_FOLDER`: Folder for uploaded files
- `TEMP_FOLDER`: Folder for temporary files
- `PROCESSED_FOLDER`: Folder for processed output files
""")

# Deployment information
st.header("Deployment Instructions")
st.write("""
This application is deployed in two parts:

1. **Flask Backend**: Deployed on Render.com to handle API requests
2. **Next.js Frontend**: Deployed on Vercel to provide the user interface
""")

st.subheader("Frontend Configuration")
st.write("""
To connect your frontend to this backend, set the following environment variable in your Vercel deployment:
```
NEXT_PUBLIC_BACKEND_API_URL=https://your-backend-api.onrender.com
```
""")

# Footer
st.markdown("---")
st.caption(f"Documentation generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
