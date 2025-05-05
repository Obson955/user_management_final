from builtins import range
import pytest
from uuid import UUID
from sqlalchemy import select
from app.models.user_model import User, UserRole
from app.models.role_change_history import RoleChangeHistory
from app.services.role_service import RoleService
from app.services.event_service import EventService, EventTypes

pytestmark = pytest.mark.asyncio

# Test getting available roles
async def test_get_available_roles():
    roles = await RoleService.get_available_roles()
    assert len(roles) == 4  # ANONYMOUS, AUTHENTICATED, MANAGER, ADMIN
    assert "ANONYMOUS" in roles
    assert "AUTHENTICATED" in roles
    assert "MANAGER" in roles
    assert "ADMIN" in roles

# Test changing a user's role with valid data
async def test_change_user_role_valid(db_session, user, admin_user):
    # Make sure the user has AUTHENTICATED role before we start
    user.role = UserRole.AUTHENTICATED
    db_session.add(user)
    await db_session.commit()
    
    # Ensure user has a different role than what we're changing to
    assert user.role == UserRole.AUTHENTICATED
    
    # Change the user's role
    role_change_result = await RoleService.change_user_role(
        db_session,
        user.id,
        UserRole.MANAGER,
        admin_user.id,
        "Testing role change"
    )
    
    # Verify the result
    assert role_change_result is not None
    assert role_change_result["user_id"] == user.id
    assert role_change_result["previous_role"] == UserRole.AUTHENTICATED.name
    assert role_change_result["new_role"] == UserRole.MANAGER.name
    assert role_change_result["changed_by"] == admin_user.email
    assert role_change_result["reason"] == "Testing role change"
    
    # Verify the user's role was updated in the database
    updated_user = await db_session.get(User, user.id)
    assert updated_user.role == UserRole.MANAGER
    
    # Verify a role change history record was created
    query = select(RoleChangeHistory).filter(RoleChangeHistory.user_id == user.id)
    query_result = await db_session.execute(query)
    history_record = query_result.scalars().first()
    
    assert history_record is not None
    assert history_record.user_id == user.id
    assert history_record.changed_by_id == admin_user.id
    assert history_record.previous_role == role_change_result["previous_role"]
    assert history_record.new_role == UserRole.MANAGER.name
    assert history_record.reason == "Testing role change"

# Test changing a user's role with non-existent user
async def test_change_user_role_nonexistent_user(db_session, admin_user):
    non_existent_id = UUID('00000000-0000-0000-0000-000000000000')
    
    result = await RoleService.change_user_role(
        db_session,
        non_existent_id,
        UserRole.MANAGER,
        admin_user.id
    )
    
    assert result is not None
    assert "error" in result
    assert "status" in result
    assert result["status"] == "not_found"
    assert f"User with ID {non_existent_id} not found" in result["error"]

# Test changing a user's role with non-existent admin
async def test_change_user_role_nonexistent_admin(db_session, user):
    non_existent_id = UUID('00000000-0000-0000-0000-000000000000')
    
    result = await RoleService.change_user_role(
        db_session,
        user.id,
        UserRole.MANAGER,
        non_existent_id
    )
    
    assert result is not None
    assert "error" in result
    assert "status" in result
    assert result["status"] == "not_found"
    assert f"User with ID {non_existent_id} not found" in result["error"]

# Test role change validation - valid change
async def test_validate_role_change_valid(db_session, user, admin_user):
    is_valid, message = await RoleService.validate_role_change(
        db_session,
        user.id,
        UserRole.MANAGER.name,
        admin_user.id
    )
    
    assert is_valid is True
    assert message == "Role change is valid"

# Test role change validation - user already has role
async def test_validate_role_change_same_role(db_session, admin_user):
    is_valid, message = await RoleService.validate_role_change(
        db_session,
        admin_user.id,
        UserRole.ADMIN.name,
        admin_user.id
    )
    
    assert is_valid is False
    assert "already has the role" in message

# Test role change validation - non-admin cannot change roles
async def test_validate_role_change_non_admin(db_session, user, verified_user):
    is_valid, message = await RoleService.validate_role_change(
        db_session,
        verified_user.id,
        UserRole.MANAGER.name,
        user.id  # Non-admin user
    )
    
    assert is_valid is False
    assert "Only administrators can change user roles" in message

# Test role change validation - cannot change last admin's role
async def test_validate_role_change_last_admin(db_session, admin_user):
    # First, make sure there's only one admin
    query = select(User).filter(User.role == UserRole.ADMIN)
    result = await db_session.execute(query)
    admins = result.scalars().all()
    
    # If there's more than one admin, we need to delete the extras for this test
    if len(admins) > 1:
        for admin in admins[1:]:
            await db_session.delete(admin)
        await db_session.commit()
    
    # Now try to change the last admin's role
    is_valid, message = await RoleService.validate_role_change(
        db_session,
        admin_user.id,
        UserRole.MANAGER.name,
        admin_user.id
    )
    
    assert is_valid is False
    assert "Cannot change the role of the last administrator" in message

# Test role change validation - invalid role string
async def test_validate_role_change_invalid_role(db_session, user, admin_user):
    # Try to change to a non-existent role
    is_valid, message = await RoleService.validate_role_change(
        db_session,
        user.id,
        "SUPER_USER",  # This role doesn't exist
        admin_user.id
    )
    
    assert is_valid is False
    assert "Invalid role: SUPER_USER" in message

# Test getting role change history
async def test_get_role_change_history(db_session, user, admin_user):
    # Create a role change to have some history
    await RoleService.change_user_role(
        db_session,
        user.id,
        UserRole.MANAGER,
        admin_user.id,
        "Testing history"
    )
    
    # Get the history
    history_data = await RoleService.get_role_change_history(
        db_session,
        user.id
    )
    
    assert history_data["total"] >= 1
    assert len(history_data["records"]) >= 1
    
    latest_record = history_data["records"][0]
    assert latest_record.user_id == user.id
    assert latest_record.changed_by_id == admin_user.id
    assert latest_record.new_role == UserRole.MANAGER.name
    assert latest_record.reason == "Testing history"

# Test event publishing when role is changed
async def test_role_change_event_publishing(db_session, user, admin_user):
    # Mock the EventService.publish method
    original_publish = EventService.publish
    publish_called = False
    
    def mock_publish(event_type, data):
        nonlocal publish_called
        publish_called = True
        assert event_type == EventTypes.USER_ROLE_CHANGED
        assert data["user_id"] == user.id
        assert data["previous_role"] == user.role.name
        assert data["new_role"] == UserRole.MANAGER.name
        assert data["changed_by"] == admin_user.email
    
    EventService.publish = mock_publish
    
    try:
        # Change the user's role
        await RoleService.change_user_role(db_session, user.id, UserRole.MANAGER, admin_user.id, "Testing event publishing")
        assert publish_called, "EventService.publish was not called"
    finally:
        # Restore the original method
        EventService.publish = original_publish

# Test role change succeeds even when event publishing fails
async def test_role_change_with_event_publishing_failure(db_session, user, admin_user):
    # Make sure the user has a different role than what we're changing to
    user.role = UserRole.AUTHENTICATED
    db_session.add(user)
    await db_session.commit()
    
    # Mock the EventService.publish method to raise an exception
    original_publish = EventService.publish
    
    def mock_publish_with_error(event_type, data):
        raise Exception("Simulated event publishing failure")
    
    EventService.publish = mock_publish_with_error
    
    try:
        # Change the user's role - this should succeed despite the event publishing failure
        result = await RoleService.change_user_role(
            db_session, 
            user.id, 
            UserRole.MANAGER, 
            admin_user.id, 
            "Testing event publishing failure"
        )
        
        # Verify the role change was successful
        assert result is not None
        assert result["user_id"] == user.id
        assert result["previous_role"] == UserRole.AUTHENTICATED.name
        assert result["new_role"] == UserRole.MANAGER.name
        
        # Verify the user's role was updated in the database
        updated_user = await db_session.get(User, user.id)
        assert updated_user.role == UserRole.MANAGER
    finally:
        # Restore the original method
        EventService.publish = original_publish
