#!/bin/bash
# Build script for DigitalOcean Functions with dependencies

set -e

echo "Building subscription-check function..."

# Create virtual environment
virtualenv --without-pip virtualenv

# Install dependencies
pip3 install -r requirements.txt --target virtualenv/lib/python3.9/site-packages

echo "Build complete!"
