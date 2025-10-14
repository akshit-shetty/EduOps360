import pandas as pd
import sqlite3
import os
import argparse
import sys


def excel_to_sqlite(file_path=None, target_db_path=None):
    # For web server usage, file_path should always be provided
    if not file_path:
        print("No file path provided. Exiting.")
        return False

    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}. Exiting.")
        return False

    try:
        # Step 2: Load Excel file and ensure proper closure
        with pd.ExcelFile(file_path) as excel_file:
            sheet_names = excel_file.sheet_names
            print(f"Sheets found: {sheet_names}")
            
            # Read all sheets into memory to avoid keeping file open
            sheet_data = {}
            for sheet in sheet_names:
                sheet_data[sheet] = pd.read_excel(excel_file, sheet_name=sheet)

        # Step 3: Connect to existing database or use default
        if target_db_path:
            db_name = target_db_path
            print(f"Using target database: {db_name}")
        else:
            # Fallback to original behavior if no target specified
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            db_name = f"{base_name}.db"
            print(f"Creating new database: {db_name}")
        
        # Connect to database with proper error handling
        conn = sqlite3.connect(db_name)
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous=NORMAL")  # Better performance
        
        # Get existing tables in database
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"Existing tables in database: {existing_tables}")

        # Step 4: Only update tables that have corresponding Excel sheets
        updated_tables = []
        skipped_sheets = []
        
        for sheet in sheet_names:
            try:
                df = sheet_data[sheet]  # Use pre-loaded data
                
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
                
                # Update/create table for this sheet
                df.to_sql(sheet, conn, if_exists="replace", index=False)
                updated_tables.append(sheet)
                print(f"✅ Sheet '{sheet}' updated as table with {len(df)} rows")
                print(f"   Columns: {cleaned_columns}")
                
            except Exception as sheet_error:
                print(f"❌ Error processing sheet '{sheet}': {sheet_error}")
                skipped_sheets.append(sheet)

        # Step 5: Report what was preserved
        preserved_tables = [table for table in existing_tables if table not in updated_tables]
        if preserved_tables:
            print(f"🔒 Preserved existing tables: {preserved_tables}")
        
        # Summary
        print(f"\n📊 Update Summary:")
        print(f"   • Updated tables: {len(updated_tables)} - {updated_tables}")
        print(f"   • Preserved tables: {len(preserved_tables)} - {preserved_tables}")
        if skipped_sheets:
            print(f"   • Skipped sheets: {len(skipped_sheets)} - {skipped_sheets}")

        # Step 6: Close connection
        conn.close()
        print("Database update completed. Connection closed.")
        return True
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert Excel to SQLite')
    parser.add_argument('--file', type=str, required=True, help='Path to Excel file to process')
    parser.add_argument('--target-db', type=str, help='Path to target SQLite database (optional)')
    args = parser.parse_args()
    
    success = excel_to_sqlite(args.file, args.target_db if hasattr(args, 'target_db') else None)
    sys.exit(0 if success else 1)