#!/bin/bash

# Deploy script for the Invoice Processor backend
echo "Preparing to deploy the Invoice Processor backend..."

# Create necessary directories
mkdir -p uploads temp processed

# Ensure all Python files are executable
chmod +x *.py

# Install dependencies
pip install -r requirements.txt

# Start the application with gunicorn
gunicorn app.main:app
