#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install production dependencies
pip install -r requirements.txt

# Gather static assets via WhiteNoise
python manage.py collectstatic --no-input

# Run migrations and one-command demo loader (categories, transactions, initial categorization)
python manage.py setup_demo
