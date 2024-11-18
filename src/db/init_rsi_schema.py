"""Schema initialization for RSI integration tables"""

import logging
import asyncpg
from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger('DraXon_OCULUS')

async def init_rsi_schema(settings):
    """Initialize RSI database schema"""
    try:
        # Connect directly with asyncpg to run migrations
        conn = await asyncpg.connect(settings.database_url)
        
        # Create tables if they don't exist, preserve existing data
        await conn.execute("""
            BEGIN;
            
            -- Create RSI members table if it doesn't exist
            CREATE TABLE IF NOT EXISTS rsi_members (
                discord_id TEXT PRIMARY KEY,
                handle TEXT UNIQUE,
                sid TEXT,
                display_name TEXT,
                enlisted TIMESTAMP WITH TIME ZONE,
                org_status TEXT,
                org_rank TEXT,
                org_stars INTEGER DEFAULT 0,
                verified BOOLEAN DEFAULT FALSE,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                raw_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create indices
            CREATE INDEX IF NOT EXISTS rsi_members_handle_idx ON rsi_members(handle);
            CREATE INDEX IF NOT EXISTS rsi_members_sid_idx ON rsi_members(sid);
            
            -- Create role history table if it doesn't exist
            CREATE TABLE IF NOT EXISTS role_history (
                id SERIAL PRIMARY KEY,
                discord_id TEXT REFERENCES rsi_members(discord_id) ON DELETE CASCADE,
                old_rank TEXT,
                new_rank TEXT,
                reason TEXT,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create verification history table if it doesn't exist
            CREATE TABLE IF NOT EXISTS verification_history (
                id SERIAL PRIMARY KEY,
                discord_id TEXT REFERENCES rsi_members(discord_id) ON DELETE CASCADE,
                action TEXT,
                status BOOLEAN,
                details JSONB,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create incident history table if it doesn't exist
            CREATE TABLE IF NOT EXISTS incident_history (
                guid TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT,
                components JSONB,
                link TEXT,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            COMMIT;
        """)
        
        await conn.close()
        logger.info("RSI schema initialization complete")

    except Exception as e:
        logger.error(f"Error initializing RSI schema: {e}")
        raise
