#!/bin/bash
set -e

# Connect to the database and execute the SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create schema if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'prices_db') THEN
            EXECUTE 'CREATE SCHEMA prices_db';
        END IF;
    END
    \$\$;

    -- Create tables if not exists
    CREATE TABLE IF NOT EXISTS prices_db.crypto_currencies (
        id SERIAL PRIMARY KEY,
        token_name VARCHAR(25) NOT NULL,
        date DATE NOT NULL,
        price_usd NUMERIC(38,2) NOT NULL,
        dw_timestamp TIMESTAMP DEFAULT now() NOT NULL
    );

    CREATE TABLE IF NOT EXISTS prices_db.steam_skins (
        id SERIAL PRIMARY KEY,
        skin_name VARCHAR(25) NOT NULL,
        date DATE NOT NULL,
        price_usd NUMERIC(38,2) NOT NULL,
        dw_timestamp TIMESTAMP DEFAULT now() NOT NULL
    );

    CREATE TABLE IF NOT EXISTS prices_db.stocks_tinkoff (
        id SERIAL PRIMARY KEY,
        ticker_name VARCHAR(25) NOT NULL,
        date DATE NOT NULL,
        price_rub NUMERIC(38,2) NOT NULL,
        dw_timestamp TIMESTAMP DEFAULT now() NOT NULL
    );

    CREATE TABLE IF NOT EXISTS prices_db.stocks_ibkr (
        id SERIAL PRIMARY KEY,
        ticker_name VARCHAR(25) NOT NULL,
        date DATE NOT NULL,
        price_usd NUMERIC(38,2) NOT NULL,
        dw_timestamp TIMESTAMP DEFAULT now() NOT NULL
    );
	
	CREATE TABLE IF NOT EXISTS prices_db.currency_rates (
        id SERIAL PRIMARY KEY,
        base_currency VARCHAR(25) NOT NULL,
        exchange_currency VARCHAR(25) NOT NULL,
        date DATE NOT NULL,
        rate NUMERIC(38,2) NOT NULL,
        dw_timestamp TIMESTAMP DEFAULT now() NOT NULL
    );
	
    -- Create user and grant permissions
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'test') THEN
            CREATE ROLE test LOGIN PASSWORD 'test';
        END IF;
    END
    \$\$;

    GRANT USAGE ON SCHEMA prices_db TO test;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA prices_db TO test;

    -- Ensure future tables also have permissions granted
    ALTER DEFAULT PRIVILEGES IN SCHEMA prices_db GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO test;
EOSQL
