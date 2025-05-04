from builtins import dict, str
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class EventService:
    """
    Simple event service for publishing events within the application.
    This is a minimal implementation focused on logging events.
    """
    
    @classmethod
    def publish(cls, event_type: str, data: Dict[str, Any]) -> None:
        """
        Publish an event by logging it.
        
        Args:
            event_type: The type of event being published
            data: The data associated with the event
        """
        logger.info(f"Event published: {event_type} with data: {data}")


# Define event types as constants
class EventTypes:
    """Constants for event types used in the application."""
    USER_ROLE_CHANGED = "user_role_changed"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
