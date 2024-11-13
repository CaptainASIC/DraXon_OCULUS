"""Schema initialization for DraXon OCULUS v3"""

import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.schema import CreateTable

from src.db.v3_models import (
    Base,
    DraXonDivision,
    DraXonMember,
    DraXonPosition,
    DraXonApplication,
    DraXonVote,
    DraXonAuditLog
)

logger = logging.getLogger('DraXon_OCULUS')

async def init_v3_schema(settings):
    """Initialize v3 database schema"""
    try:
        # Create SQLAlchemy engine using the existing connection pool
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # Drop existing tables in reverse order
        tables = [
            'v3_audit_logs',
            'v3_votes',
            'v3_applications',
            'v3_positions',
            'v3_members',
            'v3_divisions'
        ]
        
        with engine.connect() as connection:
            for table in tables:
                if inspector.has_table(table):
                    connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    logger.info(f"Dropped table: {table}")
            connection.commit()
        
        # Create tables in correct order due to foreign key dependencies
        tables = [
            DraXonDivision.__table__,
            DraXonMember.__table__,
            DraXonPosition.__table__,
            DraXonApplication.__table__,
            DraXonVote.__table__,
            DraXonAuditLog.__table__
        ]
        
        # Create each table
        for table in tables:
            Base.metadata.create_all(bind=engine, tables=[table])
            logger.info(f"Created table: {table.name}")

        # Insert default divisions
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

def get_create_table_sql():
    """Get SQL statements for creating tables"""
    tables = [
        DraXonDivision.__table__,
        DraXonMember.__table__,
        DraXonPosition.__table__,
        DraXonApplication.__table__,
        DraXonVote.__table__,
        DraXonAuditLog.__table__
    ]
    
    sql_statements = []
    for table in tables:
        sql = str(CreateTable(table).compile()).strip() + ";"
        sql_statements.append(sql)
    
    return "\n\n".join(sql_statements)

def get_table_names():
    """Get list of v3 table names"""
    return [
        'v3_divisions',
        'v3_members',
        'v3_positions',
        'v3_applications',
        'v3_votes',
        'v3_audit_logs'
    ]
