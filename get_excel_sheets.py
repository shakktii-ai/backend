import pandas as pd
import sys
import json

def get_excel_sheets(file_path):
    try:
        # Load Excel file
        xls = pd.ExcelFile(file_path)
        
        # Get sheet names
        sheet_names = xls.sheet_names
        
        # Return sheet names as JSON
        print(json.dumps({"sheets": sheet_names}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        get_excel_sheets(sys.argv[1])
    else:
        print(json.dumps({"error": "No file path provided"}))
