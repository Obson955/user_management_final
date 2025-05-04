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
    """
    
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
                logger.error(f"User with ID {user_id} not found")
                return None
                
            # Get the user who is making the change
            changed_by = await session.get(User, changed_by_id)
            if not changed_by:
                logger.error(f"User with ID {changed_by_id} not found")
                return None
                
            # Check if the new role is valid
            try:
                new_role_enum = UserRole[new_role.name] if isinstance(new_role, UserRole) else UserRole[new_role]
            except (KeyError, ValueError):
                logger.error(f"Invalid role: {new_role}")
                return None
                
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
            EventService.publish(EventTypes.USER_ROLE_CHANGED, role_change_data)
            
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
                                     limit: int = 10) -> Tuple[List[RoleChangeHistory], int]:
        """
        Get the role change history for a specific user or all users.
        
        Args:
            session: The database session
            user_id: Optional ID of the user to get history for. If None, get history for all users.
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return (for pagination)
            
        Returns:
            A tuple containing a list of role change history records and the total count
        """
        try:
            # Build the query
            query = select(RoleChangeHistory)
            count_query = select(func.count()).select_from(RoleChangeHistory)
            
            # Filter by user_id if provided
            if user_id:
                query = query.filter(RoleChangeHistory.user_id == user_id)
                count_query = count_query.filter(RoleChangeHistory.user_id == user_id)
            
            # Apply pagination
            query = query.order_by(RoleChangeHistory.changed_at.desc()).offset(skip).limit(limit)
            
            # Execute the queries
            result = await session.execute(query)
            count_result = await session.execute(count_query)
            
            # Get the results
            history_records = result.scalars().all()
            total_count = count_result.scalar()
            
            return history_records, total_count
            
        except Exception as e:
            logger.error(f"Error getting role change history: {e}")
            return [], 0
    
    @classmethod
    async def get_available_roles(cls) -> List[str]:
        """
        Get a list of all available roles in the system.
        
        Returns:
            A list of role names
        """
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
            try:
                new_role_enum = UserRole[new_role] if isinstance(new_role, str) else UserRole[new_role.name]
            except (KeyError, ValueError):
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
            logger.error(f"Error validating role change: {e}")
            return False, f"Error validating role change: {str(e)}"
