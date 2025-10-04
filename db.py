import pandas as pd
import sqlite3
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import os
import argparse
import sys

def excel_to_sqlite(file_path=None):
    if not file_path:
        # Step 1: Ask user to upload Excel file (original behavior)
        Tk().withdraw()  # Hide the root Tk window
        file_path = askopenfilename(
            title="Select Excel file", 
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
    else:
        # Use the provided file path
        file_path = file_path

    if not file_path or not os.path.exists(file_path):
        print("File does not exist. Exiting.")
        return False

    try:
        # Step 2: Load Excel file
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
        print(f"Sheets found: {sheet_names}")

        # Step 3: Create/connect SQLite database
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        db_name = f"{base_name}.db"
        conn = sqlite3.connect(db_name)
        print(f"Database '{db_name}' connected/created.")

        # Step 4: Iterate sheets and create/update tables
        for sheet in sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)
            
            # Keep original column names with spaces, but handle duplicates
            original_columns = df.columns.tolist()
            cleaned_columns = []
            seen_columns = {}
            
            for col in original_columns:
                # Keep the original column name with spaces
                base_col = str(col)
                
                # Handle duplicates by appending number
                if base_col in seen_columns:
                    seen_columns[base_col] += 1
                    final_col = f"{base_col} {seen_columns[base_col]}"
                else:
                    seen_columns[base_col] = 1
                    final_col = base_col
                
                cleaned_columns.append(final_col)
            
            df.columns = cleaned_columns
            
            # 'replace' ensures:
            # - if table exists: delete previous entries and recreate
            # - if table doesn't exist: create new table
            df.to_sql(sheet, conn, if_exists="replace", index=False)
            print(f"Sheet '{sheet}' has been added/updated as a table.")
            print(f"Columns: {cleaned_columns}")

        # Step 5: Close connection
        conn.close()
        print("All sheets have been imported/updated. Connection closed.")
        return True
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert Excel to SQLite')
    parser.add_argument('--file', type=str, help='Path to Excel file to process')
    args = parser.parse_args()
    
    if args.file:
        success = excel_to_sqlite(args.file)
        sys.exit(0 if success else 1)
    else:
        excel_to_sqlite()