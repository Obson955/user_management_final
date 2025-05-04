from builtins import str
import pytest
from httpx import AsyncClient
from uuid import UUID
from app.main import app
from app.models.user_model import User, UserRole

pytestmark = pytest.mark.asyncio

# Test getting available roles as admin
async def test_get_available_roles_as_admin(async_client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.get("/roles/available", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "roles" in data
    assert len(data["roles"]) == 4
    assert "ADMIN" in data["roles"]
    assert "MANAGER" in data["roles"]
    assert "AUTHENTICATED" in data["roles"]
    assert "ANONYMOUS" in data["roles"]

# Test getting available roles without admin privileges
async def test_get_available_roles_unauthorized(async_client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await async_client.get("/roles/available", headers=headers)
    
    assert response.status_code == 403

# Test changing a user's role as admin
async def test_change_user_role_as_admin(async_client, verified_user, admin_token, db_session):
    # First, ensure the user has AUTHENTICATED role
    verified_user.role = UserRole.AUTHENTICATED
    db_session.add(verified_user)
    await db_session.commit()
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    role_change_data = {
        "new_role": "MANAGER",
        "reason": "Promotion for good performance"
    }
    
    response = await async_client.put(
        f"/roles/users/{verified_user.id}",
        json=role_change_data,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(verified_user.id)
    assert data["previous_role"] == "AUTHENTICATED"
    assert data["new_role"] == "MANAGER"
    assert data["reason"] == "Promotion for good performance"

# Test changing a user's role without admin privileges
async def test_change_user_role_unauthorized(async_client, verified_user, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    role_change_data = {
        "new_role": "MANAGER",
        "reason": "Promotion for good performance"
    }
    
    response = await async_client.put(
        f"/roles/users/{verified_user.id}",
        json=role_change_data,
        headers=headers
    )
    
    assert response.status_code == 403

# Test changing a user's role to an invalid role
async def test_change_user_role_invalid_role(async_client, verified_user, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    role_change_data = {
        "new_role": "INVALID_ROLE",
        "reason": "Testing invalid role"
    }
    
    response = await async_client.put(
        f"/roles/users/{verified_user.id}",
        json=role_change_data,
        headers=headers
    )
    
    assert response.status_code == 422  # Validation error

# Test changing a non-existent user's role
async def test_change_nonexistent_user_role(async_client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    role_change_data = {
        "new_role": "MANAGER",
        "reason": "Testing non-existent user"
    }
    
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = await async_client.put(
        f"/roles/users/{non_existent_id}",
        json=role_change_data,
        headers=headers
    )
    
    assert response.status_code == 400  # Bad request

# Test changing a user to the same role they already have
async def test_change_user_to_same_role(async_client, admin_user, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    role_change_data = {
        "new_role": "ADMIN",  # Admin user already has ADMIN role
        "reason": "Testing same role"
    }
    
    response = await async_client.put(
        f"/roles/users/{admin_user.id}",
        json=role_change_data,
        headers=headers
    )
    
    assert response.status_code == 400  # Bad request
    assert "already has the role" in response.json()["detail"]

# Test getting role change history as admin
async def test_get_role_history_as_admin(async_client, verified_user, admin_user, admin_token):
    # First, make a role change to ensure there's history
    headers = {"Authorization": f"Bearer {admin_token}"}
    role_change_data = {
        "new_role": "MANAGER",
        "reason": "Creating history for test"
    }
    
    await async_client.put(
        f"/roles/users/{verified_user.id}",
        json=role_change_data,
        headers=headers
    )
    
    # Now get the history
    response = await async_client.get("/roles/history", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    
    # Check that our role change is in the history
    found = False
    for item in data["items"]:
        if (item["user_id"] == str(verified_user.id) and 
            item["new_role"] == "MANAGER" and 
            item["reason"] == "Creating history for test"):
            found = True
            break
    
    assert found is True

# Test getting role change history for a specific user
async def test_get_user_role_history(async_client, verified_user, admin_user, admin_token):
    # First, make a role change to ensure there's history
    headers = {"Authorization": f"Bearer {admin_token}"}
    role_change_data = {
        "new_role": "MANAGER",
        "reason": "Creating user-specific history"
    }
    
    await async_client.put(
        f"/roles/users/{verified_user.id}",
        json=role_change_data,
        headers=headers
    )
    
    # Now get the history for this specific user
    response = await async_client.get(f"/roles/history/{verified_user.id}", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    
    # All items should be for this user
    for item in data["items"]:
        assert item["user_id"] == str(verified_user.id)
    
    # Check that our role change is in the history
    found = False
    for item in data["items"]:
        if (item["new_role"] == "MANAGER" and 
            item["reason"] == "Creating user-specific history"):
            found = True
            break
    
    assert found is True

# Test getting role change history without admin privileges
async def test_get_role_history_unauthorized(async_client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await async_client.get("/roles/history", headers=headers)
    
    assert response.status_code == 403
