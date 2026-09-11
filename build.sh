#!/usr/bin/env bash
# Exit on any error
set -o errexit

# Install production dependencies
pip install -r requirements.txt

# Collect static files into STATIC_ROOT using WhiteNoise
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Seed initial super food menu and operational settings (idempotent)
python manage.py seed_nutrient_data
