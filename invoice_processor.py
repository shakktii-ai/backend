"""
Invoice Processing Module

This module adapts the perfect4.py script to work as part of a Flask backend API.
It handles invoice processing using AI techniques to extract relevant information
and automatically populate a structured format, including Chart of Accounts.
"""

import os
import sys
import pandas as pd
import PyPDF2
import anthropic
import json
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import traceback

# Import necessary functions from perfect4.py
# Later we'll copy the essential functions directly into this file

def safe_print(message):
    """Safely print messages, handling encoding issues."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode('utf-8', errors='replace').decode('ascii', errors='replace'))

def extract_text_from_pdf(pdf_path):
    """Extract text content from a PDF file."""
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n\n"
        return text
    except Exception as e:
        safe_print(f"Error extracting text from PDF: {str(e)}")
        return ""

def read_excel_sheet(excel_path, sheet_name=None):
    """Read a specific sheet from an Excel file."""
    try:
        if sheet_name:
            return pd.read_excel(excel_path, sheet_name=sheet_name)
        else:
            # Get all sheet names
            xls = pd.ExcelFile(excel_path)
            sheet_names = xls.sheet_names
            
            # Use the first sheet if none specified
            if sheet_names:
                return pd.read_excel(excel_path, sheet_name=sheet_names[0])
            else:
                raise ValueError("No sheets found in the Excel file")
    except Exception as e:
        safe_print(f"Error reading Excel file: {str(e)}")
        raise

def extract_first_json(text):
    """Extract the first JSON object from the text."""
    try:
        # Look for JSON between code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        
        if json_match:
            json_str = json_match.group(1)
            # Try to parse the JSON
            return json.loads(json_str)
        
        # If no code blocks, try to find JSON directly
        # Find the position of the first '{' and the last '}'
        start_pos = text.find('{')
        end_pos = text.rfind('}')
        
        if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
            json_str = text[start_pos:end_pos+1]
            return json.loads(json_str)
        
        raise ValueError("No JSON found in the text")
    except Exception as e:
        safe_print(f"Error extracting JSON: {str(e)}")
        safe_print(f"Text snippet: {text[:100]}...")
        raise ValueError(f"Failed to extract JSON: {str(e)}")

def construct_prompt(coa_sheet, structure, invoice_text):
    """Construct a prompt for Claude to classify the invoice."""
    # Convert COA sheet to a string representation
    coa_data = []
    for _, row in coa_sheet.iterrows():
        row_data = []
        for col in structure['columns']:
            if col in row:
                row_data.append(f"{col}: {row[col]}")
        coa_data.append(", ".join(row_data))
    
    coa_text = "\n".join(coa_data)
    
    # Create the prompt
    prompt = f"""
I need your help classifying this invoice according to our Chart of Accounts (COA).

Here's the invoice text:
---
{invoice_text}
---

Here's our Chart of Accounts structure:
{coa_text}

Please analyze the invoice and extract the following information in JSON format:
"""
    
    # Add expected fields to the prompt
    for col in structure['columns']:
        prompt += f"- {col}\n"
    
    prompt += """
Respond ONLY with a JSON object containing these fields. Format numbers according to these rules:
- Account codes should be formatted as numbers with leading zeros if needed
- Monetary amounts should be decimal numbers

Example response format:
```json
{{
"""

    # Add example fields to the JSON
    example_fields = []
    for col in structure['columns']:
        example_fields.append(f'  "{col}": "value"')
    
    prompt += ",\n".join(example_fields)
    prompt += """
}
```
"""
    
    return prompt

def classify_invoice_with_claude(invoice_text, coa_sheet, structure, api_key):
    """Uses Claude API to classify invoice data and match it to the Chart of Accounts."""
    # Get the structure analysis
    prompt = construct_prompt(coa_sheet, structure, invoice_text)

    safe_print("\\nSending prompt to Claude API...")
    
    # Set a system prompt specifically requesting JSON response
    system_prompt = """
    You are a financial analysis assistant. When producing JSON output:
    1. Always enclose the entire JSON in a code block with ```json and ``` markers
    2. Ensure the JSON is well-formed and valid
    3. Provide a single JSON object, not an array of objects
    4. Follow the exact schema requested by the user
    """
    
    # Call the Claude API
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4000,
        temperature=0,
        system=system_prompt,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    response_text = message.content[0].text
    
    # Use our safe_print for Claude's response that might contain Unicode characters
    try:
        safe_print("\\nClaude Response (Preview): " + response_text[:100] + "...")
    except:
        safe_print("\\nClaude Response received but cannot be displayed due to encoding issues.")

    try:
        extracted_data = extract_first_json(response_text)
        safe_print("\\nJSON successfully extracted.")
        
        # Check if extracted data is a list/array, and if so, use the first item
        if isinstance(extracted_data, list) and len(extracted_data) > 0:
            safe_print(f"Extracted data is an array with {len(extracted_data)} items. Using the first item.")
            item_data = extracted_data[0]  # Use the first item in the list
        else:
            item_data = extracted_data
            
        # Ensure all required columns are present and properly formatted
        final_data = {}
        for col in structure['columns']:
            # Get the value directly from extracted_data
            value = item_data.get(col, "")
            
            # Apply formatting based on column type
            if col in structure['patterns']:
                pattern = structure['patterns'][col]
                try:
                    if pattern['type'] == '2-digit' and value:
                        # Handle both integer and decimal values
                        if '.' in str(value):
                            value = f"{int(float(str(value))):02d}"
                        else:
                            value = f"{int(str(value)):02d}"
                    elif pattern['type'] == '4-digit' and value:
                        # Handle both integer and decimal values
                        if '.' in str(value):
                            value = f"{int(float(str(value))):04d}"
                        else:
                            value = f"{int(str(value)):04d}"
                    elif pattern['type'] == 'decimal' and value:
                        # Ensure decimal format
                        value = f"{float(str(value)):.1f}"
                except (ValueError, TypeError) as e:
                    safe_print(f"Warning: Could not format value '{value}' for column '{col}': {str(e)}")
                    # Keep original value if formatting fails
                    pass
            
            # Store the value in final_data
            final_data[col] = value
        
        safe_print("\\nFinal Data to be inserted: [Data prepared successfully]")
        return final_data

    except Exception as e:
        raise ValueError(f"Error processing Claude's response: {str(e)}\\nRaw output:\\n{response_text}")

def add_to_excel(excel_path, sheet_name, classified_data):
    """Add the classified data as a new row in the Excel file."""
    try:
        # Read the Excel file
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        
        # Convert classified_data to a DataFrame row
        new_row = pd.DataFrame([classified_data])
        
        # Append the new row
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Save the updated Excel file
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return True
    except Exception as e:
        safe_print(f"Error adding data to Excel: {str(e)}")
        return False

def process_invoice(coa_path, invoice_path, sheet_name=None, existing_file_path=None):
    """
    Process an invoice against a chart of accounts.
    
    Args:
        coa_path: Path to the chart of accounts Excel file
        invoice_path: Path to the invoice PDF file
        sheet_name: Name of the sheet in the Excel file (optional)
        existing_file_path: Path to an existing processed file to update (optional)
        
    Returns:
        dict: Result information including success status and output file path
    """
    try:
        # Get API key from environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": "Anthropic API key not found in environment variables"
            }
        
        # Extract text from invoice
        safe_print(f"Extracting text from invoice: {invoice_path}")
        invoice_text = extract_text_from_pdf(invoice_path)
        if not invoice_text:
            return {
                "success": False,
                "error": "Failed to extract text from the invoice PDF"
            }
        
        # Read COA Excel file
        safe_print(f"Reading chart of accounts: {coa_path}")
        try:
            if sheet_name:
                coa_sheet = read_excel_sheet(coa_path, sheet_name)
            else:
                # Try to get all sheets and use the first one
                xls = pd.ExcelFile(coa_path)
                sheet_names = xls.sheet_names
                sheet_name = sheet_names[0] if sheet_names else None
                if not sheet_name:
                    return {
                        "success": False,
                        "error": "No sheets found in the Excel file"
                    }
                coa_sheet = pd.read_excel(coa_path, sheet_name=sheet_name)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read Excel file: {str(e)}"
            }
        
        # Define the structure for the chart of accounts
        structure = {
            "columns": [
                "Account Code", "Account Name", "Description", "Amount", 
                "Tax Code", "Tax Amount", "Date", "Invoice Number"
            ],
            "patterns": {
                "Account Code": {"type": "4-digit"},
                "Tax Code": {"type": "2-digit"},
                "Amount": {"type": "decimal"},
                "Tax Amount": {"type": "decimal"}
            }
        }
        
        # Classify the invoice using Claude
        safe_print("Classifying invoice with Claude API...")
        try:
            classified_data = classify_invoice_with_claude(invoice_text, coa_sheet, structure, api_key)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to classify invoice: {str(e)}"
            }
        
        # Determine output file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if existing_file_path and os.path.exists(existing_file_path):
            # Use existing file
            output_file_path = existing_file_path
        else:
            # Create a new file
            basename = os.path.basename(coa_path)
            filename, ext = os.path.splitext(basename)
            # Create processed_output directory if it doesn't exist
            processed_dir = os.path.join(tempfile.gettempdir(), "processed_output")
            os.makedirs(processed_dir, exist_ok=True)
            # Generate new filename
            output_file_path = os.path.join(
                processed_dir,
                f"{filename}_combined_{timestamp}{ext}"
            )
            # Copy the original file
            shutil.copy2(coa_path, output_file_path)
        
        # Add classified data to the Excel file
        safe_print(f"Adding classified data to Excel: {output_file_path}")
        success = add_to_excel(output_file_path, sheet_name, classified_data)
        
        if not success:
            return {
                "success": False,
                "error": "Failed to add data to Excel file"
            }
        
        safe_print(f"Invoice processing completed successfully. Output file: {output_file_path}")
        
        return {
            "success": True,
            "output_file_path": output_file_path,
            "details": {
                "invoice_name": os.path.basename(invoice_path),
                "coa_name": os.path.basename(coa_path),
                "sheet_name": sheet_name,
                "processed_file": os.path.basename(output_file_path),
                "timestamp": timestamp
            }
        }
        
    except Exception as e:
        error_details = traceback.format_exc()
        safe_print(f"Error in process_invoice: {str(e)}\n{error_details}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
