from builtins import str
from datetime import datetime
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.user_model import UserRole

class RoleChangeHistory(Base):
    """
    Represents a history record of role changes within the application.
    This class tracks when a user's role was changed, who changed it,
    and what the previous and new roles were.
    
    Attributes:
        id (UUID): Unique identifier for the role change record.
        user_id (UUID): The ID of the user whose role was changed.
        changed_by_id (UUID): The ID of the user who performed the role change.
        previous_role (UserRole): The role the user had before the change.
        new_role (UserRole): The role the user was changed to.
        changed_at (datetime): The timestamp when the role change occurred.
        reason (str): Optional reason for the role change.
    """
    __tablename__ = "role_change_history"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    changed_by_id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    previous_role: Mapped[str] = Column(String(50), nullable=False)
    new_role: Mapped[str] = Column(String(50), nullable=False)
    changed_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str] = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="role_changes")
    changed_by = relationship("User", foreign_keys=[changed_by_id])

    def __repr__(self) -> str:
        """Provides a readable representation of a role change record."""
        return f"<RoleChange for user {self.user_id}, from {self.previous_role} to {self.new_role}>"
