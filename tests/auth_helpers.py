"""Provision authenticated databases for existing business regression tests."""
from salon_core import SalonDatabase as Database


def SalonDatabase(path):
    db = Database(path)
    if not db.has_accounts():
        db.setup_manager('manager', 'test-manager-password')
    db.login('manager', 'test-manager-password')
    return db
