#!/usr/bin/env bash
# Render build command
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py init_schema        # creates the "inventory" schema on first deploy
python manage.py migrate
