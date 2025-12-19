-- Drop existing incorrectly structured table
DROP TABLE IF EXISTS trading_sessions CASCADE;

-- Remove the faked migration record so we can re-run it
DELETE FROM django_migrations WHERE app = 'signals' AND name = '0024_tradingsession';
