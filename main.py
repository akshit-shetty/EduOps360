"""
Appwrite Functions entry point for EduOps360
This file serves as the main entry point for Appwrite Functions deployment
"""

import os
import sys
import json
from flask import Flask
from werkzeug.serving import WSGIRequestHandler

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main Flask application
from app import app

def main(context):
    """
    Main entry point for Appwrite Functions
    
    Args:
        context: Appwrite function context containing request data
    
    Returns:
        Response object for Appwrite Functions
    """
    try:
        # Extract request information from context
        method = context.req.method or 'GET'
        path = context.req.path or '/'
        headers = context.req.headers or {}
        body = context.req.body or ''
        
        # Set up environment for Flask app
        os.environ.setdefault('FLASK_ENV', 'production')
        os.environ.setdefault('PORT', '3000')
        
        # Create a test client to handle the request
        with app.test_client() as client:
            # Convert headers to proper format
            flask_headers = {}
            for key, value in headers.items():
                flask_headers[key] = value
            
            # Make request to Flask app
            if method.upper() == 'GET':
                response = client.get(path, headers=flask_headers)
            elif method.upper() == 'POST':
                response = client.post(path, data=body, headers=flask_headers)
            elif method.upper() == 'PUT':
                response = client.put(path, data=body, headers=flask_headers)
            elif method.upper() == 'DELETE':
                response = client.delete(path, headers=flask_headers)
            else:
                response = client.get(path, headers=flask_headers)
            
            # Return response in Appwrite Functions format
            return context.res.json({
                'statusCode': response.status_code,
                'headers': dict(response.headers),
                'body': response.get_data(as_text=True)
            })
            
    except Exception as e:
        # Log error and return error response
        context.log(f"Error in main function: {str(e)}")
        return context.res.json({
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        })

# Alternative entry point for direct execution
if __name__ == '__main__':
    # This runs when the file is executed directly (not as Appwrite Function)
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"Starting EduOps360 on port {port}")
    print(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
