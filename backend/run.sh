#!/bin/bash

# Minnets Backend Startup Script

set -e

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "   Copy env.template to .env and add your API keys:"
    echo "   cp env.template .env"
    echo ""
    exit 1
fi

# Run the server
echo ""
echo "🧠 Starting Minnets backend..."
echo "   Server: http://127.0.0.1:8000"
echo "   Docs:   http://127.0.0.1:8000/docs"
echo ""

python main.py

