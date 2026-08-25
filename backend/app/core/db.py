"""
Re-export database base and session utilities for app.core interface.
"""

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.session import (
    check_db_connection,
    connect_with_retry,
    dispose_engine,
    get_db,
)

__all__ = [
    "Base",
    "UUIDPrimaryKeyMixin",
    "CreatedAtMixin",
    "TimestampMixin",
    "get_db",
    "check_db_connection",
    "connect_with_retry",
    "dispose_engine",
]
