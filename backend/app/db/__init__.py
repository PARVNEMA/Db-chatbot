# Import all domain models so SQLAlchemy registers them in the declarative mapper registry
import app.domain.auth.models  # noqa: F401
import app.domain.chat.models  # noqa: F401
import app.domain.connections.models  # noqa: F401
import app.domain.projects.models  # noqa: F401
import app.domain.schema_introspection.models  # noqa: F401
import app.domain.semantic_layer.models  # noqa: F401
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
