#!/usr/bin/env python3
"""
Database migration management script
"""
import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from alembic.config import Config
from alembic import command
from config import settings

def run_migrations(target='head', sql=False, tag=None):
    """Run database migrations"""
    alembic_cfg = Config("alembic.ini")
    
    # Set database URL
    database_url = os.getenv('DATABASE_URL', settings.DATABASE_URL)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    
    try:
        if sql:
            command.upgrade(alembic_cfg, target, sql=True)
        else:
            command.upgrade(alembic_cfg, target, tag=tag)
        print(f"Migrations applied successfully to {target}")
        return True
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

def create_migration(message, autogenerate=True):
    """Create a new migration"""
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.revision(
            alembic_cfg,
            message=message,
            autogenerate=autogenerate
        )
        print(f"Migration created: {message}")
        return True
    except Exception as e:
        print(f"Failed to create migration: {e}")
        return False

def check_status():
    """Check migration status"""
    from alembic.script import ScriptDirectory
    
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    print(f"Current head revision: {script.get_current_head()}")
    
    # Check for unapplied migrations
    command.current(alembic_cfg, verbose=True)

def main():
    parser = argparse.ArgumentParser(description="Database migration manager")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade database')
    upgrade_parser.add_argument('target', nargs='?', default='head', help='Target revision')
    upgrade_parser.add_argument('--sql', action='store_true', help='Generate SQL only')
    upgrade_parser.add_argument('--tag', help='Tag to apply')
    
    # Downgrade command
    downgrade_parser = subparsers.add_parser('downgrade', help='Downgrade database')
    downgrade_parser.add_argument('target', help='Target revision')
    downgrade_parser.add_argument('--sql', action='store_true', help='Generate SQL only')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create migration')
    create_parser.add_argument('message', help='Migration message')
    create_parser.add_argument('--no-autogenerate', action='store_true', help='Disable autogenerate')
    
    # Status command
    subparsers.add_parser('status', help='Check migration status')
    
    # History command
    subparsers.add_parser('history', help='Show migration history')
    
    # Current command
    subparsers.add_parser('current', help='Show current revision')
    
    args = parser.parse_args()
    
    if args.command == 'upgrade':
        run_migrations(args.target, args.sql, args.tag)
    elif args.command == 'downgrade':
        command.downgrade(Config("alembic.ini"), args.target, sql=args.sql)
    elif args.command == 'create':
        create_migration(args.message, not args.no_autogenerate)
    elif args.command == 'status':
        check_status()
    elif args.command == 'history':
        command.history(Config("alembic.ini"), verbose=True)
    elif args.command == 'current':
        command.current(Config("alembic.ini"), verbose=True)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
