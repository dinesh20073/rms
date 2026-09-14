#!/bin/bash
# Build script for Vercel deployment
set -e

echo "=== Installing dependencies ==="
python -m pip install -r requirements.txt

echo "=== Running database migrations ==="
python manage.py migrate --no-input

echo "=== Bundling in-memory templates ==="
python ems_core/bundle_templates.py

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input --clear

echo "=== Build complete ==="
