#!/bin/bash

# EduOps360 Startup Script for Cloud Deployment
echo "🚀 Starting EduOps360..."

# Set default environment variables
export FLASK_ENV=${FLASK_ENV:-production}
export PORT=${PORT:-3000}
export HOST=${HOST:-0.0.0.0}

# Check if database exists
if [ -f "eduops360.db" ]; then
    echo "✅ Database file found"
    chmod 664 eduops360.db
else
    echo "⚠️  Database file not found - will be created on first run"
fi

# Check Python version
echo "🐍 Python version: $(python --version)"

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the application
echo "🌐 Starting server on $HOST:$PORT"
echo "🔧 Environment: $FLASK_ENV"

# Use server.py if it exists, otherwise fall back to app.py
if [ -f "server.py" ]; then
    echo "🎯 Using production server (server.py)"
    python server.py
elif [ -f "app.py" ]; then
    echo "🎯 Using application server (app.py)"
    python app.py
else
    echo "❌ No server file found!"
    exit 1
fi
