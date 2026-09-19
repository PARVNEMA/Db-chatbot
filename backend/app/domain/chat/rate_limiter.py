"""Chat domain — Rate Limiting & Cooldown Engine (Phase 7).

Enforces safety rate limits and execution cooldowns to prevent spamming,
runaway automation, and repeated cascading transaction failures:
- Max 3 active pending mutations per session.
- Max 30 executed write transactions per project per hour.
- Max 200 total rows written per project per hour.
- 60-second execution failure cooldown per session.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.domain.chat.models import MutationAuditLog, PendingMutation

logger = logging.getLogger(__name__)

MAX_PENDING_MUTATIONS_PER_SESSION = 3
MAX_WRITES_PER_PROJECT_PER_HOUR = 30
MAX_ROWS_WRITTEN_PER_PROJECT_PER_HOUR = 200
FAILURE_COOLDOWN_SECONDS = 60.0


class MutationRateLimiter:
    """In-memory and persistent rate limiter for database write operations."""

    def __init__(self) -> None:
        # Tracks last failure timestamp keyed by session_id
        self._session_failure_timestamps: dict[uuid.UUID, float] = {}

    def record_failure(self, session_id: uuid.UUID) -> None:
        """Record an execution failure timestamp for the session cooldown."""
        self._session_failure_timestamps[session_id] = time.perf_counter()
        logger.info("Recorded execution failure cooldown for session %s", session_id)

    def clear_failure_cooldown(self, session_id: uuid.UUID) -> None:
        """Clear the failure cooldown for a session (e.g. on test teardown)."""
        self._session_failure_timestamps.pop(session_id, None)

    def check_failure_cooldown(self, session_id: uuid.UUID) -> None:
        """Verify the session is not in a post-failure cooldown.

        Raises:
            BadRequestException: If within 60s of a previous failure.
        """
        last_failed = self._session_failure_timestamps.get(session_id)
        if last_failed is not None:
            elapsed = time.perf_counter() - last_failed
            if elapsed < FAILURE_COOLDOWN_SECONDS:
                remaining = int(FAILURE_COOLDOWN_SECONDS - elapsed)
                raise BadRequestException(
                    detail=(
                        f"Execution cooldown active: please wait {remaining}s before attempting "
                        "another write mutation after a failed execution."
                    ),
                    error_code="WRITE_COOLDOWN_ACTIVE",
                )
            else:
                # Cooldown expired, cleanup entry
                self._session_failure_timestamps.pop(session_id, None)

    async def check_session_pending_limit(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        """Verify the session has not exceeded the max pending mutations cap."""
        stmt = (
            select(func.count())
            .select_from(PendingMutation)
            .where(
                PendingMutation.project_id == project_id,
                PendingMutation.session_id == session_id,
                PendingMutation.status.in_(["PENDING_APPROVAL", "COLLECTING_INPUT"]),
            )
        )
        count = (await db.execute(stmt)).scalar_one()
        if count >= MAX_PENDING_MUTATIONS_PER_SESSION:
            raise BadRequestException(
                detail=(
                    f"Session pending mutation cap reached ({count}/{MAX_PENDING_MUTATIONS_PER_SESSION}). "
                    "Please approve or reject existing pending mutations before planning new writes."
                ),
                error_code="MAX_PENDING_MUTATIONS_REACHED",
            )

    async def check_project_hourly_limits(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> None:
        """Enforce 30 writes/hour and 200 rows/hour write caps per project."""
        cutoff = datetime.now(tz=UTC) - timedelta(hours=1)

        stmt = select(
            func.count(MutationAuditLog.id),
            func.coalesce(func.sum(MutationAuditLog.total_rows_affected), 0),
        ).where(
            MutationAuditLog.project_id == project_id,
            MutationAuditLog.status == "executed",
            MutationAuditLog.created_at >= cutoff,
        )
        result = (await db.execute(stmt)).one()
        hourly_mutations = result[0]
        hourly_rows = result[1]

        if hourly_mutations >= MAX_WRITES_PER_PROJECT_PER_HOUR:
            raise BadRequestException(
                detail=(
                    f"Hourly project write limit exceeded ({hourly_mutations}/{MAX_WRITES_PER_PROJECT_PER_HOUR} writes in past hour). "
                    "Please wait for the rolling hour window to reset."
                ),
                error_code="HOURLY_WRITE_LIMIT_EXCEEDED",
            )

        if hourly_rows >= MAX_ROWS_WRITTEN_PER_PROJECT_PER_HOUR:
            raise BadRequestException(
                detail=(
                    f"Hourly project row write cap exceeded ({hourly_rows}/{MAX_ROWS_WRITTEN_PER_PROJECT_PER_HOUR} rows in past hour). "
                    "Safety limit prevents further write operations for 1 hour."
                ),
                error_code="HOURLY_ROW_CAP_EXCEEDED",
            )

    async def check_all_write_limits(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        """Run all rate limit checks before planning or staging a mutation."""
        self.check_failure_cooldown(session_id=session_id)
        await self.check_session_pending_limit(db=db, project_id=project_id, session_id=session_id)
        await self.check_project_hourly_limits(db=db, project_id=project_id)


# Global singleton instance
mutation_rate_limiter = MutationRateLimiter()
