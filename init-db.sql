-- Initialize databases for ASCII Backend
-- This script runs automatically when PostgreSQL container starts for the first time

-- Create database for Module A (Consent & Request Receipt Inbox)
CREATE DATABASE ascii_a;

-- Create database for Module B (Eraser & Revocation Concierge)
CREATE DATABASE ascii_b;

-- Grant privileges to postgres user
GRANT ALL PRIVILEGES ON DATABASE ascii_a TO postgres;
GRANT ALL PRIVILEGES ON DATABASE ascii_b TO postgres;

