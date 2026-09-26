#!/usr/bin/env bash
# Exit on any error
set -o errexit

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Seeding initial nutrient data..."
python manage.py seed_nutrient_data

echo "==> Starting Gunicorn web server..."
exec gunicorn food_delivery.wsgi:application --bind 0.0.0.0:${PORT:-8000}
