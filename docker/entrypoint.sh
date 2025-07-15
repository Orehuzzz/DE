#!/bin/bash

# Wait for the Postgres database to be available
echo "Waiting for Postgres to start..."
./wait-for-it.sh postgres:5432 --timeout=30

# Upgrade the Airflow database
echo "Upgrading the Airflow database..."
airflow db upgrade

# Continue with the original entry point command
exec "$@"
