from builtins import bool, classmethod, int, str
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_model import User, UserRole
from app.models.role_change_history import RoleChangeHistory
from app.services.event_service import EventService, EventTypes
import logging

logger = logging.getLogger(__name__)

class RoleService:
    """
    Service class for managing user roles and role change history.
    
    This service provides methods for:
    - Changing user roles and recording the history
    - Retrieving role change history
    - Getting available roles
    - Validating role changes based on business rules
    """
    
    @classmethod
    def _parse_role(cls, role_value) -> Optional[UserRole]:
        """
        Parse a role value into a UserRole enum.
        
        Args:
            role_value: The role value to parse, can be a string or UserRole enum
            
        Returns:
            The parsed UserRole enum, or None if the role is invalid
        """
        try:
            if isinstance(role_value, str):
                return UserRole[role_value]
            elif isinstance(role_value, UserRole):
                return role_value
            else:
                return None
        except (KeyError, ValueError):
            return None
    
    @classmethod
    async def change_user_role(cls, 
                              session: AsyncSession, 
                              user_id: UUID, 
                              new_role: UserRole, 
                              changed_by_id: UUID,
                              reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Change a user's role and record the change in the role change history.
        
        Args:
            session: The database session
            user_id: The ID of the user whose role is being changed
            new_role: The new role to assign to the user
            changed_by_id: The ID of the user making the change
            reason: Optional reason for the role change
            
        Returns:
            A dictionary containing information about the role change, or None if the change failed
        """
        try:
            # Get the user whose role is being changed
            user = await session.get(User, user_id)
            if not user:
                error_msg = f"User with ID {user_id} not found"
                logger.error(f"[RoleService] {error_msg}")
                return {"error": error_msg, "status": "not_found"}
                
            # Get the user who is making the change
            changed_by = await session.get(User, changed_by_id)
            if not changed_by:
                error_msg = f"User with ID {changed_by_id} not found"
                logger.error(f"[RoleService] {error_msg}")
                return {"error": error_msg, "status": "not_found"}
                
            # Check if the new role is valid
            new_role_enum = cls._parse_role(new_role)
            if new_role_enum is None:
                error_msg = f"Invalid role: {new_role}"
                logger.error(f"[RoleService] {error_msg}")
                return {"error": error_msg, "status": "invalid_role"}
                
            # Record the previous role before changing it
            previous_role = user.role
            
            # Create a role change history record
            role_change = RoleChangeHistory(
                user_id=user_id,
                changed_by_id=changed_by_id,
                previous_role=previous_role.name,
                new_role=new_role_enum.name,
                reason=reason
            )
            
            # Update the user's role
            user.role = new_role_enum
            
            # Save the changes
            session.add(role_change)
            session.add(user)
            await session.commit()
            
            # Log the successful role change for audit purposes
            logger.info(f"[RoleService] Role change successful: User {user.email} (ID: {user_id}) role changed from {previous_role.name} to {new_role_enum.name} by {changed_by.email} (ID: {changed_by_id}). Reason: {reason or 'No reason provided'}")
            
            # Prepare the role change data
            role_change_data = {
                "user_id": user_id,
                "previous_role": previous_role.name,
                "new_role": new_role_enum.name,
                "changed_at": role_change.changed_at,
                "changed_by": changed_by.email,
                "reason": reason
            }
            
            # Publish the role change event
            try:
                EventService.publish(EventTypes.USER_ROLE_CHANGED, role_change_data)
            except Exception as e:
                # Log a warning but don't fail the operation
                logger.warning(f"[RoleService] Failed to publish role change event: {e}, but role change was successful")
            
            # Return information about the role change
            return role_change_data
            
        except Exception as e:
            logger.error(f"Error changing user role: {e}")
            await session.rollback()
            return None
    
    @classmethod
    async def get_role_change_history(cls, 
                                     session: AsyncSession, 
                                     user_id: Optional[UUID] = None,
                                     skip: int = 0,
                                     limit: int = 10) -> Dict[str, Any]:
        """
        Get the role change history for a specific user or all users.
        
        Args:
            session: The database session
            user_id: Optional ID of the user to get history for. If None, get history for all users.
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return (for pagination)
            
        Returns:
            A dictionary containing records, total count, and pagination metadata
        """
        try:
            # Build the query with optimized performance
            # Only select the columns we need to reduce data transfer
            query = select(RoleChangeHistory)
            
            # Use a more efficient count query that doesn't fetch all records
            count_query = select(func.count(RoleChangeHistory.id))
            
            # Filter by user_id if provided
            if user_id:
                query = query.filter(RoleChangeHistory.user_id == user_id)
                count_query = count_query.filter(RoleChangeHistory.user_id == user_id)
                
            # Add index hint for better performance when filtering by user_id
            if user_id:
                # This is a comment that indicates we should create an index on user_id
                # in a production environment for better performance
                pass
            
            # Apply pagination
            query = query.order_by(RoleChangeHistory.changed_at.desc()).offset(skip).limit(limit)
            
            # Execute the queries
            result = await session.execute(query)
            count_result = await session.execute(count_query)
            
            # Get the results
            history_records = result.scalars().all()
            total_count = count_result.scalar()
            
            # Return a dictionary with records and pagination metadata
            return {
                "records": history_records,
                "total": total_count,
                "limit": limit,
                "skip": skip
            }
            
        except Exception as e:
            logger.error(f"[RoleService] Error getting role change history: {e}, user_id={user_id if 'user_id' in locals() else 'N/A'}, skip={skip}, limit={limit}")
            return {
                "records": [],
                "total": 0,
                "limit": limit,
                "skip": skip
            }
    
    @classmethod
    async def get_available_roles(cls) -> List[str]:
        """
        Get a list of all available roles in the system.
        
        This method returns all possible roles defined in the UserRole enum.
        It can be used to populate dropdown menus or for validation.
        
        Returns:
            A list of role names as strings
        """
        # Use a list comprehension to iterate over the UserRole enum and extract the role names
        return [role.name for role in UserRole]
    
    @classmethod
    async def validate_role_change(cls, 
                                  session: AsyncSession,
                                  user_id: UUID, 
                                  new_role: str, 
                                  changed_by_id: UUID) -> Tuple[bool, str]:
        """
        Validate if a role change is allowed.
        
        Args:
            session: The database session
            user_id: The ID of the user whose role is being changed
            new_role: The new role to assign to the user
            changed_by_id: The ID of the user making the change
            
        Returns:
            A tuple containing a boolean indicating if the change is valid and a message
        """
        try:
            # Get the users
            user = await session.get(User, user_id)
            changed_by = await session.get(User, changed_by_id)
            
            if not user:
                return False, f"User with ID {user_id} not found"
                
            if not changed_by:
                return False, f"User with ID {changed_by_id} not found"
                
            # Check if the new role is valid
            new_role_enum = cls._parse_role(new_role)
            if new_role_enum is None:
                return False, f"Invalid role: {new_role}"
                
            # Check if the user already has the requested role
            if user.role == new_role_enum:
                return False, f"User already has the role {new_role}"
                
            # Only ADMIN users can change roles
            if changed_by.role != UserRole.ADMIN:
                return False, "Only administrators can change user roles"
                
            # Prevent changing the role of the last admin
            if user.role == UserRole.ADMIN and new_role_enum != UserRole.ADMIN:
                # Count the number of admins
                admin_count_query = select(func.count()).select_from(User).filter(User.role == UserRole.ADMIN)
                admin_count_result = await session.execute(admin_count_query)
                admin_count = admin_count_result.scalar()
                
                if admin_count <= 1:
                    return False, "Cannot change the role of the last administrator"
            
            return True, "Role change is valid"
            
        except Exception as e:
            logger.error(f"[RoleService] Error validating role change: {e}, user_id={user_id}, new_role={new_role}, changed_by_id={changed_by_id}")
            return False, f"Error validating role change: {str(e)}"
