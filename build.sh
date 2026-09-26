#!/usr/bin/env bash
# Exit on any error
set -o errexit

echo "==> Installing production dependencies..."
pip install -r requirements.txt

echo "==> Collecting static assets..."
python manage.py collectstatic --no-input
