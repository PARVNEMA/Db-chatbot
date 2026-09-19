"""Agent domain — Mutation Previewer Node (Phase 5).

Fetches candidate matching rows for PATCH operations, computes tamper-evident hashes,
encrypts change-sets, persists PendingMutation records in PENDING_APPROVAL state,
and emits 'mutation_preview' and 'mutation_approval_required' frames over WebSocket.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.security import encrypt_secret
from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.state import AgentState
from app.domain.chat.repository import PendingMutationRepository

logger = logging.getLogger(__name__)


def compute_change_set_hash(change_set: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of canonicalized JSON change-set."""
    canonical_json = json.dumps(change_set, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def create_mutation_previewer_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the mutation previewer and HITL staging node."""

    async def mutation_previewer_node(state: AgentState) -> dict[str, Any]:
        """Preview candidate records, persist PendingMutation, and request owner approval."""
        change_set = state.get("mutation_change_set")
        project_id = state["project_id"]
        session_id = state["session_id"]
        connection_id = state["connection_id"]

        logger.info(
            "--- [Node: mutation_previewer] INPUT ---\n"
            "  Session: %s\n"
            "  Project: %s",
            session_id,
            project_id,
        )

        if not change_set:
            return {
                "mutation_status": "validation_failed",
                "mutation_validation_error": "No change-set proposal available for preview staging.",
            }

        preview_row_counts: dict[str, int] = {}
        patch_candidate_previews: dict[str, list[dict[str, Any]]] = {}
        mutations = change_set.get("mutations", [])

        # 1. Candidate row preview for PATCH operations
        for m in mutations:
            table_name = m.get("table", "")
            op = m.get("operation", "insert").lower()

            if op == "insert":
                count = len(m.get("rows", []))
                preview_row_counts[table_name] = preview_row_counts.get(table_name, 0) + count

            elif op == "patch":
                # Execute safe candidate preview query if connection manager is available
                patch_filter = m.get("filter") or {}
                candidate_rows: list[dict[str, Any]] = []

                if patch_filter and deps.connection_manager is not None:
                    # Construct parameterized equality WHERE clause
                    where_clauses: list[str] = []
                    params: dict[str, Any] = {}
                    for idx, (k, v) in enumerate(patch_filter.items()):
                        param_name = f"p_{idx}"
                        where_clauses.append(f"{k} = :{param_name}")
                        params[param_name] = v

                    where_sql = " AND ".join(where_clauses)
                    limit = deps.connection.max_patch_rows_per_table + 1
                    preview_query = f"SELECT * FROM {table_name} WHERE {where_sql} LIMIT {limit}"

                    try:
                        candidate_rows = await deps.connection_manager.execute_safe(
                            project_id=project_id,
                            connection_id=connection_id,
                            sql=preview_query,
                            params=params,
                        )
                    except Exception as exc:
                        logger.warning("Could not execute candidate preview query for %s: %s", table_name, exc)

                if patch_filter and len(candidate_rows) == 0 and deps.connection_manager is not None:
                    # Filter did not match any rows
                    return {
                        "mutation_status": "validation_failed",
                        "mutation_validation_error": (
                            f"PATCH filter {patch_filter} on table '{table_name}' matches 0 candidate rows. "
                            "No rows exist to update."
                        ),
                    }

                count = len(candidate_rows) if candidate_rows else len(m.get("rows", [1]))
                if count > deps.connection.max_patch_rows_per_table:
                    return {
                        "mutation_status": "validation_failed",
                        "mutation_validation_error": (
                            f"PATCH filter matches {count} rows, which exceeds max_patch_rows_per_table "
                            f"limit of {deps.connection.max_patch_rows_per_table}."
                        ),
                    }

                preview_row_counts[table_name] = preview_row_counts.get(table_name, 0) + count
                patch_candidate_previews[table_name] = candidate_rows

        total_rows_affected = sum(preview_row_counts.values())

        # 2. Compute canonical hash and encrypt change-set payload
        change_set_hash = compute_change_set_hash(change_set)
        canonical_json = json.dumps(change_set, sort_keys=True)
        change_set_encrypted = encrypt_secret(canonical_json)

        timeout_val = getattr(deps.connection, "approval_timeout_minutes", 15)
        timeout_minutes = int(timeout_val) if isinstance(timeout_val, (int, float)) else 15
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(minutes=timeout_minutes)

        is_dry_run = bool(state.get("dry_run", False))

        async def _safe_send_event(event_type: str, data: dict[str, Any]) -> None:
            if deps.ws_manager is not None:
                try:
                    res = deps.ws_manager.send_event(
                        session_id=session_id,
                        event_type=event_type,
                        data=data,
                    )
                    if inspect.isawaitable(res):
                        await res
                except Exception as ws_err:
                    logger.warning("Could not dispatch ws event %s: %s", event_type, ws_err)

        if is_dry_run:
            logger.info("--- [Node: mutation_previewer] DRY-RUN MODE: bypassing database staging ---")
            await _safe_send_event(
                event_type="mutation_preview",
                data={
                    "dry_run": True,
                    "mutation_id": None,
                    "change_set": change_set,
                    "preview_row_counts": preview_row_counts,
                    "candidate_rows": patch_candidate_previews,
                    "total_rows_affected": total_rows_affected,
                },
            )

            lines = [
                f"### [Dry-Run] Proposed Change-Set Preview: {change_set.get('summary', '')}\n",
                f"- **Total Rows Affected:** {total_rows_affected}",
                "- **Mode:** Dry-Run (No pending mutation staged, no changes executed)",
                "**Preview Breakdown:**",
            ]
            for tbl, cnt in preview_row_counts.items():
                lines.append(f"- Table `{tbl}`: {cnt} row(s)")

            lines.append("\n> ℹ️ *Dry-run completed successfully. All validations and row previews passed.*")

            return {
                "mutation_id": None,
                "mutation_status": "DRY_RUN_COMPLETED",
                "nl_summary": "\n".join(lines),
            }

        # 4. Persist PendingMutation record in platform DB
        db_session = None
        try:
            db_session = getattr(deps, "db", None)
        except AttributeError:
            db_session = None

        pending_mutation_id = uuid.uuid4()
        if db_session is not None:
            mutation_repo = PendingMutationRepository(db_session)
            pending_mutation = await mutation_repo.create_mutation(
                project_id=project_id,
                session_id=session_id,
                connection_id=connection_id,
                proposer_id=deps.user_id,
                change_set_encrypted=change_set_encrypted,
                change_set_hash=change_set_hash,
                expires_at=expires_at,
                preview_row_counts=preview_row_counts,
                status="PENDING_APPROVAL",
            )
            pending_mutation_id = pending_mutation.id

        logger.info(
            "--- [Node: mutation_previewer] STAGED PendingMutation %s (expires: %s) ---",
            pending_mutation_id,
            expires_at.isoformat(),
        )

        # 5. Broadcast WebSocket frames for preview & approval
        # mutation_preview frame
        await _safe_send_event(
            event_type="mutation_preview",
            data={
                "mutation_id": str(pending_mutation_id),
                "change_set": change_set,
                "preview_row_counts": preview_row_counts,
                "candidate_rows": patch_candidate_previews,
                "expires_at": expires_at.isoformat(),
            },
        )

        # mutation_approval_required frame
        await _safe_send_event(
            event_type="mutation_approval_required",
            data={
                "mutation_id": str(pending_mutation_id),
                "summary": change_set.get("summary", "Proposed database mutation"),
                "total_rows_affected": total_rows_affected,
                "expires_at": expires_at.isoformat(),
                "approval_timeout_minutes": timeout_minutes,
            },
        )

        # 6. Build summary for user chat
        lines = [
            f"### Proposed Change-Set Preview: {change_set.get('summary', '')}\n",
            f"- **Total Rows Affected:** {total_rows_affected}",
            f"- **Pending Mutation ID:** `{pending_mutation_id}`",
            f"- **Approval Window:** {timeout_minutes} minutes (expires at {expires_at.strftime('%H:%M:%S UTC')})\n",
            "**Preview Breakdown:**",
        ]
        for tbl, cnt in preview_row_counts.items():
            lines.append(f"- Table `{tbl}`: {cnt} row(s)")

        lines.append(
            "\n> ⚠️ **Project Owner Approval Required**: "
            "Please review the changes and click **Approve** or **Reject** in the UI to execute this transaction."
        )

        return {
            "mutation_id": pending_mutation_id,
            "mutation_status": "PENDING_APPROVAL",
            "nl_summary": "\n".join(lines),
        }

    return mutation_previewer_node
