"""Agent domain — Pydantic schemas for multi-table mutation proposals and validation results (Phase 3).

Defines structured DTOs for multi-table INSERT and PATCH change-sets, mutation items,
cross-table $ref dependencies, and deterministic validation outputs.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MutationOperation = Literal["insert", "patch"]


class MutationItem(BaseModel):
    """A single atomic write operation (INSERT or PATCH) targeting a specific table."""

    model_config = ConfigDict(extra="ignore")

    sequence: int = Field(
        ...,
        description="Execution sequence order within the change-set.",
    )
    operation: MutationOperation = Field(
        ...,
        description="The write operation type: 'insert' or 'patch'.",
    )
    table: str = Field(
        ...,
        min_length=1,
        description="Target database table name.",
    )
    columns: list[str] = Field(
        default_factory=list,
        description="List of column names targeted by this mutation.",
    )
    rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of row dictionaries containing column values for INSERT or PATCH.",
    )
    filter: dict[str, Any] | None = Field(
        default=None,
        description="Filter condition for PATCH operations (e.g. {'id': 10}). Mandatory for PATCH.",
    )
    dependencies: list[int] = Field(
        default_factory=list,
        description="List of mutation sequences or indices that this mutation depends on.",
    )


class ChangeSetProposal(BaseModel):
    """Structured proposal representing a multi-table write transaction."""

    model_config = ConfigDict(extra="ignore")

    change_set_id: uuid.UUID | str = Field(
        default_factory=uuid.uuid4,
        description="Unique identifier for the proposed change-set.",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="Human-readable summary of the intended changes.",
    )
    expected_total_rows_affected: int = Field(
        default=0,
        ge=0,
        description="Expected total count of affected rows across all mutations in the set.",
    )
    mutations: list[MutationItem] = Field(
        default_factory=list,
        description="Ordered list of atomic mutations composing the change-set.",
    )


class ValidationErrorItem(BaseModel):
    """Specific validation violation caught by the deterministic safety rules."""

    field: str | None = None
    table: str | None = None
    message: str
    code: str


class MutationValidationResult(BaseModel):
    """Result of deterministic pre-execution validation checks on a change-set proposal."""

    is_valid: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_rows: int = 0
    table_names: list[str] = Field(default_factory=list)

    @property
    def error_summary(self) -> str:
        """Combine all validation error messages into a single human-readable string."""
        return "; ".join(e.message for e in self.errors)
