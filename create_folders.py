from flask import Flask, jsonify, request, render_template, Blueprint
import os
import pandas as pd
import csv
from io import StringIO
import tempfile
import subprocess

folders_bp = Blueprint("folders", __name__)

def open_folder_dialog():
    """Open a folder dialog using tkinter"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Hide the main tkinter window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        # Open folder dialog
        folder_path = filedialog.askdirectory(
            title="Select where to create folders"
        )
        
        root.destroy()
        return folder_path
        
    except Exception as e:
        print(f"Error with tkinter dialog: {e}")
        # Fallback to manual input
        return None

@folders_bp.route("/")
def folder_home():
    return render_template("folder_creator_ui.html")


@folders_bp.route('/get_folder_path', methods=['GET'])
def get_folder_path():
    """Open a folder dialog and return the selected path"""
    try:
        # Open folder selection dialog
        folder_path = open_folder_dialog()
        
        if folder_path:
            return jsonify({
                'success': True,
                'path': folder_path
            })
        else:
            # Return a specific error to trigger a better UI response
            return jsonify({
                'success': False,
                'error': 'dialog_unavailable',
                'message': 'Folder dialog is not available in this environment'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Error opening folder dialog'
        }), 500
        
@folders_bp.route('/upload_file', methods=['POST'])
def upload_file():
    """Handle CSV or Excel file upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is CSV or Excel
        if not (file.filename.lower().endswith('.csv') or file.filename.lower().endswith('.xlsx')):
            return jsonify({'error': 'File must be a CSV or Excel (.xlsx) file'}), 400
        
        folder_names = []
        
        # Process CSV file
        if file.filename.lower().endswith('.csv'):
            # Read CSV content
            csv_content = file.stream.read().decode('utf-8')
            csv_file = StringIO(csv_content)
            
            # Parse CSV
            reader = csv.reader(csv_file)
            for row in reader:
                if row and row[0] and str(row[0]).strip():  # First column, non-empty
                    folder_names.append(str(row[0]).strip())
        
        # Process Excel file
        elif file.filename.lower().endswith('.xlsx'):
            # Read Excel file
            file.stream.seek(0)  # Reset stream position
            df = pd.read_excel(file.stream)
            # Get first column values
            first_column = df.iloc[:, 0].dropna()
            # Convert to string and strip whitespace
            folder_names = [str(item).strip() for item in first_column if str(item).strip()]
        
        return jsonify({
            'success': True,
            'folder_count': len(folder_names),
            'folder_names': folder_names,
            'filename': file.filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@folders_bp.route('/create_folders', methods=['POST'])
def create_folders():
    """Create folders from file data"""
    try:
        data = request.json
        print(f"Received data: {data}")  # Debug: print received data
        
        target_path = data.get('path')
        folders = data.get('folders', [])
        
        print(f"Target path: {target_path}")  # Debug
        print(f"Folders count: {len(folders)}")  # Debug
        print(f"First few folders: {folders[:5] if folders else 'None'}")  # Debug
        
        if not target_path or not folders:
            return jsonify({
                "error": "Missing path or folders",
                "received_path": target_path,
                "received_folders_count": len(folders)
            }), 400
        
        # Create folders
        created = []
        failed = []
        
        for folder in folders:
            try:
                # Clean folder name
                safe_name = "".join(c for c in folder if c not in r'<>:"/\|?*')
                if len(safe_name) > 150:
                    safe_name = safe_name[:150]
                
                folder_path = os.path.join(target_path, safe_name)
                os.makedirs(folder_path, exist_ok=True)
                created.append(folder)
            except Exception as e:
                failed.append({"folder": folder, "error": str(e)})
        
        return jsonify({
            "success": True,
            "created": len(created),
            "failed": len(failed),
            "failed_details": failed,
            "total": len(folders)
        })
        
    except Exception as e:
        print(f"Error in create_folders: {e}")  # Debug
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)