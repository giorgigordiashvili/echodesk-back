#!/bin/bash
# Build script for DigitalOcean Functions with dependencies

set -e

echo "Building recurring-payments function..."

# Create virtual environment
virtualenv --without-pip virtualenv

# Install only requests (the only dependency needed)
pip3 install -r requirements.txt --target virtualenv/lib/python3.11/site-packages --no-deps
pip3 install certifi charset-normalizer idna urllib3 --target virtualenv/lib/python3.11/site-packages --no-deps

echo "Build complete!"
