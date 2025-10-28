#!/bin/bash
# Build script for DigitalOcean Functions with dependencies

set -e

echo "Building recurring-payments function..."

# Create virtual environment
virtualenv --without-pip virtualenv

# Install dependencies
pip install -r requirements.txt --target virtualenv/lib/python3.11/site-packages

echo "Build complete!"
