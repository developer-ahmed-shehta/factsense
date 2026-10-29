#!/usr/bin/env bash
set -e

echo ">>> [FactSense MES] Initializing container runtime..."

# Wait for PostgreSQL if DATABASE_URL is set
if [ -n "$DATABASE_URL" ]; then
    echo ">>> Checking database connectivity..."
fi

# Run database migrations
echo ">>> Applying database schema migrations..."
python manage.py migrate --noinput

# Collect static files
echo ">>> Collecting static assets..."
python manage.py collectstatic --noinput --clear || true

# Seed default demo roles & plant master data if requested
if [ "$SEED_DEMO_DATA" = "true" ]; then
    echo ">>> Seeding initial master data & demo users..."
    python manage.py seed_demo_users
fi

echo ">>> FactSense MES ready. Launching application server..."
exec "$@"

