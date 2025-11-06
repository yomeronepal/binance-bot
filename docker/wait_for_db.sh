#!/bin/sh

echo "Waiting for PostgreSQL to be ready..."

# Wait until PostgreSQL responds
while ! nc -z db 5432; do
  sleep 1
done

echo "PostgreSQL is up - starting Django server"

# Run Django migrations
python manage.py migrate

echo "Migrations complete - starting Daphne server..."
# Run the main command passed to the script
exec "$@"

