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
        
        # Run migrations
        await conn.execute("""
            DO $$ 
            BEGIN
                -- Alter v3_divisions
                ALTER TABLE v3_divisions 
                ALTER COLUMN role_id TYPE TEXT;
                
                -- Alter v3_members
                ALTER TABLE v3_members 
                ALTER COLUMN discord_id TYPE TEXT;
                
                -- Alter v3_applications
                ALTER TABLE v3_applications 
                ALTER COLUMN thread_id TYPE TEXT;
                
                -- Alter v3_audit_logs
                ALTER TABLE v3_audit_logs 
                ALTER COLUMN actor_id TYPE TEXT,
                ALTER COLUMN target_id TYPE TEXT;
            EXCEPTION 
                WHEN undefined_table THEN 
                    NULL;
                WHEN undefined_column THEN 
                    NULL;
            END $$;
        """)
        
        await conn.close()
        logger.info("Database migrations complete")

    except Exception as e:
        logger.error(f"Error in database migration: {e}")
        raise

    try:
        # Now create engine for table creation
        engine = create_engine(settings.database_url)
        
        # Create tables if they don't exist
        from src.db.v3_models import (
            Base,
            DraXonDivision,
            DraXonMember,
            DraXonPosition,
            DraXonApplication,
            DraXonVote,
            DraXonAuditLog
        )
        
        tables = [
            DraXonDivision.__table__,
            DraXonMember.__table__,
            DraXonPosition.__table__,
            DraXonApplication.__table__,
            DraXonVote.__table__,
            DraXonAuditLog.__table__
        ]
        
        inspector = inspect(engine)
        for table in tables:
            if not inspector.has_table(table.name):
                Base.metadata.create_all(bind=engine, tables=[table])
                logger.info(f"Created table: {table.name}")
            else:
                logger.info(f"Table already exists: {table.name}")

        # Insert default divisions if they don't exist
        from src.utils.constants import DIVISIONS
        with engine.connect() as connection:
            for name, description in DIVISIONS.items():
                connection.execute(
                    text("""
                    INSERT INTO v3_divisions (name, description)
                    VALUES (:name, :description)
                    ON CONFLICT (name) DO NOTHING
                    """),
                    {"name": name, "description": description}
                )
                connection.commit()
                logger.info(f"Created division: {name}")
        
        logger.info("V3 schema initialization complete")

    except Exception as e:
        logger.error(f"Error initializing v3 schema: {e}")
        raise
