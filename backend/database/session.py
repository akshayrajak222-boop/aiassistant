"""
database/session.py – Re-export session utilities for backward compatibility.
"""

from backend.database.connection import get_session_factory, get_engine

def AsyncSessionLocal():
    return get_session_factory()()
