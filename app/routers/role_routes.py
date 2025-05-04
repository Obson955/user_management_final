from builtins import dict, str
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_current_user, get_db, require_role
from app.models.user_model import UserRole
from app.schemas.role_schemas import (
    AvailableRolesResponse,
    RoleChangeRequest,
    RoleChangeResponse,
    RoleHistoryEntry,
    RoleHistoryResponse
)
from app.services.role_service import RoleService
from app.utils.link_generation import generate_pagination_links

router = APIRouter(
    prefix="/roles",
    tags=["Role Management"],
    responses={404: {"description": "Not found"}},
)

@router.get("/available", response_model=AvailableRolesResponse, name="get_available_roles")
async def get_available_roles(
    current_user: dict = Depends(require_role(["ADMIN"]))
):
    """
    Get a list of all available roles in the system.
    
    This endpoint returns all possible roles that can be assigned to users.
    Only administrators can access this endpoint.
    
    Returns:
        AvailableRolesResponse: A list of role names
    """
    roles = await RoleService.get_available_roles()
    return AvailableRolesResponse(roles=roles)

@router.put("/users/{user_id}", response_model=RoleChangeResponse, name="change_user_role")
async def change_user_role(
    user_id: UUID,
    role_change: RoleChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(["ADMIN"]))
):
    """
    Change a user's role.
    
    This endpoint allows administrators to change a user's role.
    The role change is recorded in the role change history.
    
    Args:
        user_id: The ID of the user whose role is being changed
        role_change: The role change request containing the new role and optional reason
        
    Returns:
        RoleChangeResponse: Information about the role change
    """
    # Validate the role change
    is_valid, message = await RoleService.validate_role_change(
        db,
        user_id,
        role_change.new_role,
        UUID(current_user["user_id"])
    )
    
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    # Perform the role change
    result = await RoleService.change_user_role(
        db,
        user_id,
        role_change.new_role,
        UUID(current_user["user_id"]),
        role_change.reason
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change user role"
        )
    
    return RoleChangeResponse(**result)

@router.get("/history", response_model=RoleHistoryResponse, name="get_role_change_history")
async def get_role_change_history(
    request: Request,
    user_id: UUID = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(["ADMIN"]))
):
    """
    Get the role change history.
    
    This endpoint returns the history of role changes for a specific user or all users.
    Only administrators can access this endpoint.
    
    Args:
        user_id: Optional ID of the user to get history for. If not provided, get history for all users.
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (for pagination)
        
    Returns:
        RoleHistoryResponse: A list of role change history records
    """
    history_records, total_count = await RoleService.get_role_change_history(
        db,
        user_id,
        skip,
        limit
    )
    
    # Generate pagination links
    pagination_links = generate_pagination_links(request, skip, limit, total_count)
    
    # Convert the history records to the response model
    items = [RoleHistoryEntry.model_validate(record) for record in history_records]
    
    return RoleHistoryResponse(
        items=items,
        total=total_count,
        links=pagination_links
    )

@router.get("/history/{user_id}", response_model=RoleHistoryResponse, name="get_user_role_change_history")
async def get_user_role_change_history(
    request: Request,
    user_id: UUID,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(["ADMIN"]))
):
    """
    Get the role change history for a specific user.
    
    This endpoint returns the history of role changes for a specific user.
    Only administrators can access this endpoint.
    
    Args:
        user_id: ID of the user to get history for
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (for pagination)
        
    Returns:
        RoleHistoryResponse: A list of role change history records for the specified user
    """
    history_records, total_count = await RoleService.get_role_change_history(
        db,
        user_id,
        skip,
        limit
    )
    
    # Generate pagination links
    pagination_links = generate_pagination_links(request, skip, limit, total_count)
    
    # Convert the history records to the response model
    items = [RoleHistoryEntry.model_validate(record) for record in history_records]
    
    return RoleHistoryResponse(
        items=items,
        total=total_count,
        links=pagination_links
    )
