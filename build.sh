#!/bin/bash

# Build script for DigitalOcean App Platform
echo "Starting build process..."

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

echo "Build completed successfully!"
