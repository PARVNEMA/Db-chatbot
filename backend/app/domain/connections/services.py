"""
Connections domain — service layer.

Orchestrates credential encryption/decryption, connectivity verification,
project ownership checks, and engine lifecycle via `ConnectionManager`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.security import decrypt, encrypt_secret
from app.dependencies.auth import DbSession
from app.domain.connections.manager import (
    ConnectionManager,
    connection_manager,
    normalize_connection_url,
)
from app.domain.connections.models import Connection
from app.domain.connections.repository import ConnectionRepository
from app.domain.connections.schemas import (
    ConnectionCreate,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectionUpdate,
)
from app.domain.projects.services import ProjectService, get_project_service


class ConnectionService:
    """Domain service managing tenant database connection operations."""

    def __init__(
        self,
        db: AsyncSession,
        project_service: ProjectService,
        manager: ConnectionManager = connection_manager,
    ) -> None:
        self._db = db
        self._project_service = project_service
        self._manager = manager
        self._repo = ConnectionRepository(db)

    async def create_connection(
        self, project_id: uuid.UUID, data: ConnectionCreate, user_id: uuid.UUID
    ) -> Connection:
        """Create and test a new connection bound to the project."""
        # 1. Enforce project ownership
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)

        # 2. Check 1:1 project-to-connection constraint
        existing = await self._repo.get_by_project_id(project_id=project_id)
        if existing is not None:
            raise ConflictException(
                detail="A database connection already exists for this project.",
                error_code="CONNECTION_ALREADY_EXISTS",
            )

        # 3. Normalize & test connectivity before committing
        normalized_conn_str = normalize_connection_url(data.connection_string)
        success, latency_ms, dialect, message = await self._manager.test_connection(
            normalized_conn_str
        )
        if not success:
            raise BadRequestException(
                detail=f"Failed to connect to target database: {message}",
                error_code="CONNECTION_TEST_FAILED",
            )

        # 4. Encrypt normalized connection string
        encrypted_conn_str = encrypt_secret(normalized_conn_str)

        # 5. Persist
        return await self._repo.create(
            project_id=project_id,
            name=data.name,
            dialect=data.dialect or dialect or "unknown",
            encrypted_connection_string=encrypted_conn_str,
        )

    async def get_connection(self, project_id: uuid.UUID, user_id: uuid.UUID) -> Connection:
        """Get project connection ensuring user ownership."""
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        connection = await self._repo.get_by_project_id(project_id=project_id)
        if connection is None:
            raise NotFoundException(
                detail=f"No connection configured for project '{project_id}'.",
                error_code="CONNECTION_NOT_FOUND",
            )
        return connection

    async def update_connection(
        self, project_id: uuid.UUID, data: ConnectionUpdate, user_id: uuid.UUID
    ) -> Connection:
        """Update existing connection attributes."""
        connection = await self.get_connection(project_id=project_id, user_id=user_id)

        encrypted_conn_str: str | None = None
        if data.connection_string:
            normalized_conn_str = normalize_connection_url(data.connection_string)
            success, _, _, message = await self._manager.test_connection(normalized_conn_str)
            if not success:
                raise BadRequestException(
                    detail=f"Updated connection string test failed: {message}",
                    error_code="CONNECTION_TEST_FAILED",
                )
            encrypted_conn_str = encrypt_secret(normalized_conn_str)
            # Invalidate old engine
            await self._manager.dispose(project_id=project_id, connection_id=connection.id)

        return await self._repo.update(
            connection=connection,
            name=data.name,
            dialect=data.dialect,
            encrypted_connection_string=encrypted_conn_str,
        )

    async def delete_connection(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete connection and dispose pooled engine."""
        connection = await self.get_connection(project_id=project_id, user_id=user_id)
        await self._manager.dispose(project_id=project_id, connection_id=connection.id)
        await self._repo.delete(connection=connection)

    async def test_connection_params(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ConnectionTestRequest | None = None,
    ) -> ConnectionTestResponse:
        """Test target database connection either with new params or stored credentials."""
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)

        if payload and payload.connection_string:
            conn_str = payload.connection_string
            dialect_hint = payload.dialect
        else:
            connection = await self.get_connection(project_id=project_id, user_id=user_id)
            conn_str = decrypt(connection.encrypted_connection_string)
            dialect_hint = connection.dialect

        success, latency_ms, detected_dialect, message = await self._manager.test_connection(
            conn_str
        )
        return ConnectionTestResponse(
            success=success,
            latency_ms=latency_ms,
            dialect=detected_dialect or dialect_hint,
            message=message,
        )


def get_connection_service(
    db: DbSession,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ConnectionService:
    """FastAPI dependency provider for ConnectionService."""
    return ConnectionService(db=db, project_service=project_service)
