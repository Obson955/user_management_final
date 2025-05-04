from builtins import str
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import re
import uuid
from app.models.user_model import UserRole
from app.schemas.pagination_schema import PaginationLink

class RoleChangeRequest(BaseModel):
    """
    Schema for requesting a role change for a user.
    """
    new_role: UserRole = Field(..., description="The new role to assign to the user")
    reason: Optional[str] = Field(None, description="Reason for the role change", max_length=255)
    
    @validator('reason')
    def validate_reason(cls, v):
        if v is not None:
            # Check for minimum length
            if len(v) < 5:
                raise ValueError('Reason must be at least 5 characters long')
            
            # Check for inappropriate content (simple example)
            inappropriate_patterns = ['profanity', 'offensive', 'inappropriate']
            for pattern in inappropriate_patterns:
                if pattern in v.lower():
                    raise ValueError(f'Reason contains inappropriate content')
        return v

class RoleChangeResponse(BaseModel):
    """
    Schema for the response after a successful role change.
    """
    user_id: uuid.UUID
    previous_role: str
    new_role: str
    changed_at: datetime
    changed_by: str
    reason: Optional[str] = None
    
    class Config:
        from_attributes = True

class RoleHistoryEntry(BaseModel):
    """
    Schema for a single entry in the role change history.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    changed_by_id: uuid.UUID
    previous_role: str
    new_role: str
    changed_at: datetime
    reason: Optional[str] = None
    
    class Config:
        from_attributes = True

class RoleHistoryResponse(BaseModel):
    """
    Schema for the response containing role change history for a user.
    """
    items: List[RoleHistoryEntry]
    total: int
    links: Optional[List[PaginationLink]] = None
    
    class Config:
        from_attributes = True

class AvailableRolesResponse(BaseModel):
    """
    Schema for the response containing all available roles in the system.
    """
    roles: List[str] = Field(..., description="List of available roles in the system")
    
    class Config:
        from_attributes = True

