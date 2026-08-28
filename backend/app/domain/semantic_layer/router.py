"""
SemanticLayer domain — FastAPI router.

Exposes REST endpoints for managing table and column semantic annotations.
Mounted under `/api/v1/projects` in `app/main.py`.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.responses import ApiResponse, success_response
from app.dependencies.auth import get_current_active_user
from app.domain.auth.models import User
from app.domain.semantic_layer.schemas import (
    AnnotationCreate,
    AnnotationResponse,
    AnnotationUpdate,
)
from app.domain.semantic_layer.services import (
    SemanticLayerService,
    get_semantic_layer_service,
)

router = APIRouter()


@router.post(
    "/{project_id}/annotations",
    response_model=ApiResponse[AnnotationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create table or column annotation",
    description="Add a business description or semantic context for a specific table or column in the project database.",
)
async def create_annotation(
    project_id: uuid.UUID,
    payload: AnnotationCreate,
    service: Annotated[SemanticLayerService, Depends(get_semantic_layer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[AnnotationResponse]:
    """Create a new schema annotation."""
    annotation = await service.create_annotation(
        project_id=project_id, user_id=current_user.id, data=payload
    )
    return success_response(
        data=AnnotationResponse.model_validate(annotation),
        message="Annotation created successfully",
    )


@router.get(
    "/{project_id}/annotations",
    response_model=ApiResponse[list[AnnotationResponse]],
    status_code=status.HTTP_200_OK,
    summary="List all schema annotations",
    description="Retrieve all table and column annotations for the project database, optionally filtered by target type.",
)
async def list_annotations(
    project_id: uuid.UUID,
    service: Annotated[SemanticLayerService, Depends(get_semantic_layer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    target_type: Literal["table", "column"] | None = Query(
        default=None, description="Filter annotations by target type ('table' or 'column')"
    ),
) -> ApiResponse[list[AnnotationResponse]]:
    """List annotations for the active project connection."""
    annotations = await service.list_annotations(
        project_id=project_id, user_id=current_user.id, target_type=target_type
    )
    return success_response(
        data=[AnnotationResponse.model_validate(a) for a in annotations],
        message="Annotations retrieved successfully",
    )


@router.get(
    "/{project_id}/annotations/{annotation_id}",
    response_model=ApiResponse[AnnotationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get single schema annotation",
    description="Fetch a specific table or column annotation by its ID.",
)
async def get_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    service: Annotated[SemanticLayerService, Depends(get_semantic_layer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[AnnotationResponse]:
    """Retrieve a single annotation."""
    annotation = await service.get_annotation(
        project_id=project_id, user_id=current_user.id, annotation_id=annotation_id
    )
    return success_response(
        data=AnnotationResponse.model_validate(annotation),
        message="Annotation retrieved successfully",
    )


@router.put(
    "/{project_id}/annotations/{annotation_id}",
    response_model=ApiResponse[AnnotationResponse],
    status_code=status.HTTP_200_OK,
    summary="Update schema annotation",
    description="Update the note content of an existing table or column annotation.",
)
async def update_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    payload: AnnotationUpdate,
    service: Annotated[SemanticLayerService, Depends(get_semantic_layer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[AnnotationResponse]:
    """Update an annotation."""
    annotation = await service.update_annotation(
        project_id=project_id,
        user_id=current_user.id,
        annotation_id=annotation_id,
        data=payload,
    )
    return success_response(
        data=AnnotationResponse.model_validate(annotation),
        message="Annotation updated successfully",
    )


@router.delete(
    "/{project_id}/annotations/{annotation_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete schema annotation",
    description="Delete a table or column annotation by its ID.",
)
async def delete_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    service: Annotated[SemanticLayerService, Depends(get_semantic_layer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[None]:
    """Delete an annotation."""
    await service.delete_annotation(
        project_id=project_id,
        user_id=current_user.id,
        annotation_id=annotation_id,
    )
    return success_response(
        data=None,
        message="Annotation deleted successfully",
    )
