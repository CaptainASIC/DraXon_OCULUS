"""Schema initialization for DraXon OCULUS v3"""

import logging
import asyncpg
from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger('DraXon_OCULUS')

async def init_v3_schema(settings):
    """Initialize v3 database schema"""
    try:
        # Connect directly with asyncpg to run migrations
        conn = await asyncpg.connect(settings.database_url)
        
        # Create tables if they don't exist, preserve existing data
        await conn.execute("""
            BEGIN;
            
            -- Create divisions table if it doesn't exist
            CREATE TABLE IF NOT EXISTS v3_divisions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                description TEXT,
                role_id TEXT
            );

            -- Create members table if it doesn't exist
            CREATE TABLE IF NOT EXISTS v3_members (
                id SERIAL PRIMARY KEY,
                discord_id TEXT UNIQUE NOT NULL,
                rank VARCHAR(3),
                division_id INTEGER REFERENCES v3_divisions(id),
                join_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'ACTIVE'
            );

            -- Create positions table if it doesn't exist
            CREATE TABLE IF NOT EXISTS v3_positions (
                id SERIAL PRIMARY KEY,
                title VARCHAR(100) NOT NULL,
                division_id INTEGER REFERENCES v3_divisions(id) NOT NULL,
                required_rank VARCHAR(3) NOT NULL,
                status VARCHAR(20) DEFAULT 'OPEN',
                holder_id INTEGER REFERENCES v3_members(id)
            );

            -- Create applications table if it doesn't exist
            CREATE TABLE IF NOT EXISTS v3_applications (
                id SERIAL PRIMARY KEY,
                applicant_id INTEGER REFERENCES v3_members(id) NOT NULL,
                position_id INTEGER REFERENCES v3_positions(id) NOT NULL,
                thread_id TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'PENDING',
                previous_experience TEXT,
                position_statement TEXT,
                additional_info TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create votes table if it doesn't exist
            CREATE TABLE IF NOT EXISTS v3_votes (
                id SERIAL PRIMARY KEY,
                application_id INTEGER REFERENCES v3_applications(id) NOT NULL,
                voter_id INTEGER REFERENCES v3_members(id) NOT NULL,
                vote VARCHAR(10) NOT NULL,
                comment TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create audit_logs table if it doesn't exist
            CREATE TABLE IF NOT EXISTS v3_audit_logs (
                id SERIAL PRIMARY KEY,
                action_type VARCHAR(50) NOT NULL,
                actor_id TEXT NOT NULL,
                target_id TEXT,
                details JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            COMMIT;
        """)
        
        # Insert default divisions if they don't exist
        from src.utils.constants import DIVISIONS
        for name, description in DIVISIONS.items():
            await conn.execute(
                """
                INSERT INTO v3_divisions (name, description)
                VALUES ($1, $2)
                ON CONFLICT (name) DO NOTHING
                """,
                name, description
            )
        
        await conn.close()
        logger.info("V3 schema initialization complete")

    except Exception as e:
        logger.error(f"Error initializing v3 schema: {e}")
        raise
