-- Create the Users
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'ferry_migrator') THEN
        CREATE USER ferry_migrator WITH PASSWORD 'migrator_pass_123';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'ferry_api_user') THEN
        CREATE USER ferry_api_user WITH PASSWORD 'api_pass_123';
    END IF;
END
$$;

-- Create the Database
CREATE DATABASE ferrytracker_db;

-- Secure the Database
REVOKE ALL ON DATABASE ferrytracker_db FROM PUBLIC;
GRANT CONNECT ON DATABASE ferrytracker_db TO ferry_migrator;
GRANT CONNECT ON DATABASE ferrytracker_db TO ferry_api_user;

-- Connect to the new DB
\c ferrytracker_db

-- Setup PostGIS and Schema Ownership
CREATE EXTENSION IF NOT EXISTS postgis;
ALTER SCHEMA public OWNER TO ferry_migrator;

-- Set Default Privileges for future objects
ALTER DEFAULT PRIVILEGES FOR USER ferry_migrator IN SCHEMA public 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ferry_api_user;

ALTER DEFAULT PRIVILEGES FOR USER ferry_migrator IN SCHEMA public 
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ferry_api_user;

-- Grant access to PostGIS tables
GRANT SELECT ON TABLE spatial_ref_sys TO ferry_api_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE geometry_columns TO ferry_api_user;