import os
import sys
import json
import uuid
import re
import shutil
import tempfile
import subprocess
import streamlit as st
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Get environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
TEMP_FOLDER = os.getenv("TEMP_FOLDER", "temp") 
PROCESSED_FOLDER = os.getenv("PROCESSED_FOLDER", "processed")

# Create necessary folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Add the current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the original Python scripts
import perfect4
import get_excel_sheets

# Set page config
st.set_page_config(
    page_title="Invoice Processor API",
    page_icon="📊",
    layout="centered"
)

# Helper functions
def allowed_file(filename, filetype=None):
    """Check if file type is allowed"""
    if filetype == 'excel':
        return filename.lower().endswith(('.xlsx', '.xls', '.csv'))
    elif filetype == 'pdf':
        return filename.lower().endswith('.pdf')
    return True

def secure_filename_custom(filename):
    """Secure a filename"""
    # Basic implementation, could be expanded
    return filename.replace(" ", "_").replace("/", "_").replace("\\", "_")

# API Endpoints as Streamlit functions
def process_invoice(coa_file, invoice_file, sheet_name="", combine_invoices=False, existing_file_path=""):
    """Process invoice using perfect4.py"""
    try:
        # Save uploaded files to temp directory
        temp_dir = TEMP_FOLDER
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create secure filenames and save files
        coa_filename = secure_filename_custom(coa_file.name)
        invoice_filename = secure_filename_custom(invoice_file.name)
        
        coa_file_path = os.path.join(temp_dir, coa_filename)
        invoice_file_path = os.path.join(temp_dir, invoice_filename)
        
        # Save the uploaded files
        with open(coa_file_path, "wb") as f:
            f.write(coa_file.getbuffer())
            
        with open(invoice_file_path, "wb") as f:
            f.write(invoice_file.getbuffer())
        
        st.write(f"Files saved: {coa_file_path}, {invoice_file_path}")
        
        # Process the invoice using perfect4.py directly
        # Build the command based on the parameters
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'perfect4.py')
        
        # Prepare command arguments
        cmd = ['python', script_path, coa_file_path, invoice_file_path]
        
        # Add sheet name if provided
        if sheet_name:
            cmd.append(sheet_name)
            
        # Add existing file path if combining invoices
        if combine_invoices and existing_file_path:
            cmd.append(existing_file_path)
            
        st.write(f"Running command: {' '.join(cmd)}")
        
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
            st.error(f"Error running perfect4.py: {process.stderr}")
            return {
                'success': False,
                'error': f"Script execution failed: {process.stderr}"
            }
            
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
            path_match = re.search(r'[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*\.xlsx', output_text)
            if path_match:
                processed_file_path = path_match.group(0)
        
        if not processed_file_path or not os.path.exists(processed_file_path):
            st.error(f"Could not find output file in script output")
            return {
                'success': False,
                'error': 'Could not determine output file path',
                'script_output': output_text
            }
            
        # Move the file to the processed folder for storage
        processed_dir = PROCESSED_FOLDER
        os.makedirs(processed_dir, exist_ok=True)
        
        # Generate a unique filename to avoid collisions
        filename = os.path.basename(processed_file_path)
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        stored_file_path = os.path.join(processed_dir, unique_filename)
        
        # Copy the file to the processed directory
        shutil.copy2(processed_file_path, stored_file_path)
        
        # Create download URL
        download_url = f"/api/download-file/{unique_filename}"
        
        return {
            'success': True,
            'message': 'Invoice processed successfully',
            'script_output': output_text,
            'file_info': {
                'path': stored_file_path,
                'filename': unique_filename,
                'download_url': download_url
            }
        }
    
    except Exception as e:
        st.error(f"Error processing invoice: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_excel_sheet_names(excel_file):
    """Get sheet names from Excel file using get_excel_sheets.py"""
    try:
        # Save the file temporarily
        temp_dir = TEMP_FOLDER
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = secure_filename_custom(excel_file.name)
        file_path = os.path.join(temp_dir, filename)
        
        # Save the uploaded file
        with open(file_path, "wb") as f:
            f.write(excel_file.getbuffer())
        
        # Try direct import first
        try:
            sheets = get_excel_sheets.get_sheets(file_path)
            return {
                'success': True,
                'sheets': sheets
            }
        except Exception as e:
            st.warning(f"Error with direct import: {str(e)}")
            
            # Fallback to subprocess
            try:
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'get_excel_sheets.py')
                process = subprocess.run(
                    ['python', script_path, file_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if process.returncode != 0:
                    return {
                        'success': False,
                        'error': f"Error getting sheets: {process.stderr}"
                    }
                    
                # Try to parse the output as JSON
                try:
                    result = json.loads(process.stdout)
                    return {
                        'success': True,
                        'sheets': result
                    }
                except json.JSONDecodeError:
                    # If not JSON, assume it's a list of sheet names separated by newlines
                    sheets = [s.strip() for s in process.stdout.strip().split('\n') if s.strip()]
                    return {
                        'success': True,
                        'sheets': sheets
                    }
                    
            except Exception as subprocess_error:
                return {
                    'success': False,
                    'error': f"Error reading Excel sheets: {str(subprocess_error)}"
                }
            
    except Exception as e:
        st.error(f"Error getting Excel sheets: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def download_processed_file(filename):
    """Serve a processed file for download"""
    try:
        file_path = os.path.join(PROCESSED_FOLDER, filename)
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f"File not found: {filename}"
            }
            
        return {
            'success': True,
            'file_path': file_path,
            'filename': filename
        }
    except Exception as e:
        st.error(f"Error preparing file for download: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# Streamlit API UI
st.title("Invoice Processor API")
st.write("This API allows you to process invoices against a chart of accounts.")

# Navigation
page = st.sidebar.selectbox("API Endpoints", ["Health Check", "Process Invoice", "Get Excel Sheets", "Download File"])

if page == "Health Check":
    st.header("Health Check")
    st.write("API Status: ✅ Healthy")
    st.json({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat()
    })
    
elif page == "Process Invoice":
    st.header("Process Invoice")
    st.write("Upload a Chart of Accounts Excel file and an Invoice PDF to process.")
    
    with st.form("process_invoice_form"):
        coa_file = st.file_uploader("Chart of Accounts Excel File", type=["xlsx", "xls", "csv"])
        invoice_file = st.file_uploader("Invoice PDF File", type=["pdf"])
        sheet_name = st.text_input("Sheet Name (Optional)")
        combine_invoices = st.checkbox("Combine Invoices")
        existing_file_path = st.text_input("Existing File Path (Optional, for combining invoices)")
        
        submit_button = st.form_submit_button("Process Invoice")
        
        if submit_button:
            if not coa_file or not invoice_file:
                st.error("Both Chart of Accounts and Invoice files are required.")
            else:
                with st.spinner("Processing invoice..."):
                    result = process_invoice(
                        coa_file=coa_file,
                        invoice_file=invoice_file,
                        sheet_name=sheet_name,
                        combine_invoices=combine_invoices,
                        existing_file_path=existing_file_path
                    )
                    
                    if result['success']:
                        st.success("Invoice processed successfully!")
                        st.json(result)
                        
                        # Provide download link
                        if 'file_info' in result and 'filename' in result['file_info']:
                            file_path = result['file_info']['path']
                            filename = result['file_info']['filename']
                            
                            with open(file_path, "rb") as file:
                                st.download_button(
                                    label="Download Processed File",
                                    data=file,
                                    file_name=filename,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                    else:
                        st.error(f"Error processing invoice: {result.get('error', 'Unknown error')}")
                        if 'script_output' in result:
                            st.code(result['script_output'])
    
elif page == "Get Excel Sheets":
    st.header("Get Excel Sheets")
    st.write("Upload an Excel file to get its sheet names.")
    
    excel_file = st.file_uploader("Excel File", type=["xlsx", "xls", "csv"])
    
    if excel_file:
        with st.spinner("Getting sheet names..."):
            result = get_excel_sheet_names(excel_file)
            
            if result['success']:
                st.success("Sheet names retrieved successfully!")
                st.json(result)
                
                # Display sheet names in a more readable format
                if 'sheets' in result and result['sheets']:
                    st.subheader("Available Sheets:")
                    for sheet in result['sheets']:
                        st.write(f"- {sheet}")
            else:
                st.error(f"Error getting sheet names: {result.get('error', 'Unknown error')}")
    
elif page == "Download File":
    st.header("Download File")
    st.write("Enter the filename to download a processed file.")
    
    filename = st.text_input("Filename")
    
    if filename:
        result = download_processed_file(filename)
        
        if result['success']:
            file_path = result['file_path']
            
            with open(file_path, "rb") as file:
                st.download_button(
                    label="Download File",
                    data=file,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.error(f"Error: {result.get('error', 'Unknown error')}")

# API Endpoint Documentation
st.sidebar.header("API Documentation")
st.sidebar.markdown("""
## Endpoints
- `/` - Health Check
- `/api/process-invoice` - Process Invoice
- `/api/get-sheets` - Get Excel Sheets
- `/api/download-file/{filename}` - Download File

For detailed documentation, refer to the README.md file.
""")

# When running this with `streamlit run streamlit_app.py`, 
# it will serve as both the UI and API for the Invoice Processor
