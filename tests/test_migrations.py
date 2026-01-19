import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text

def test_migrations_up_and_down():
    """Test that migrations can be applied and rolled back"""
    # Use test database
    engine = create_engine("sqlite:///:memory:")
    
    # Create alembic config
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///:memory:")
    
    # Apply all migrations
    command.upgrade(alembic_cfg, "head")
    
    # Verify tables exist
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]
        
        assert "accounts" in tables
        assert "transactions" in tables
        assert "ledger_entries" in tables
    
    # Rollback all migrations
    command.downgrade(alembic_cfg, "base")
    
    # Verify tables don't exist
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]
        
        assert "accounts" not in tables
        assert "transactions" not in tables
        assert "ledger_entries" not in tables

def test_migration_order():
    """Test that migrations are applied in correct order"""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "alembic")
    
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(alembic_cfg)
    
    revisions = list(script.walk_revisions())
    
    # Check that we have expected number of migrations
    assert len(revisions) >= 3
    
    # Check that down_revision links are correct
    for i, rev in enumerate(revisions):
        if i < len(revisions) - 1:
            assert rev.down_revision == revisions[i + 1].revision
