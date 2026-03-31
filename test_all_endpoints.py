#!/usr/bin/env python3
"""
Comprehensive API endpoint testing script.
Tests all endpoints and reports status codes (2xx, 4xx, 5xx).
"""
import json
import httpx
import asyncio
from collections import defaultdict
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Test credentials
TEST_EMAIL = f"testuser{int(datetime.now().timestamp())}@example.com"
TEST_PASSWORD = "SecurePass123!"
TEST_PHONE = "0123456789"

# Store test data for use across tests
test_data = {
    "access_token": None,
    "user_id": None,
    "category_id": None,
    "listing_id": None,
    "order_id": None,
}

# Results tracking
results = defaultdict(list)


async def log_result(method: str, path: str, status: int, message: str = ""):
    """Log test result."""
    status_type = "OK  " if 200 <= status < 300 else "FAIL" if status >= 400 else "REDIR"
    results[status // 100].append({
        "method": method,
        "path": path,
        "status": status,
        "message": message
    })
    print(f"{status_type} {method:6} {path:50} -> {status} {message}")


async def register_user():
    """Register a test user."""
    print("\n[1] REGISTER USER")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_V1}/auth/register",
                json={
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "full_name": "Test User",
                    "phone": TEST_PHONE
                }
            )
            if response.status_code in [200, 201]:
                data = response.json()
                test_data["access_token"] = data.get("access_token")
                test_data["user_id"] = data.get("user", {}).get("id")
                await log_result("POST", "/auth/register", response.status_code, "User created")
            else:
                await log_result("POST", "/auth/register", response.status_code, response.text[:50])
        except Exception as e:
            await log_result("POST", "/auth/register", 0, f"Error: {str(e)[:50]}")


async def login_user():
    """Login the test user."""
    print("\n[2] LOGIN USER")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_V1}/auth/login",
                data={
                    "username": TEST_EMAIL,
                    "password": TEST_PASSWORD
                }
            )
            if response.status_code in [200, 201]:
                data = response.json()
                test_data["access_token"] = data.get("access_token")
                await log_result("POST", "/auth/login", response.status_code, "Login successful")
            else:
                await log_result("POST", "/auth/login", response.status_code, response.text[:50])
        except Exception as e:
            await log_result("POST", "/auth/login", 0, f"Error: {str(e)[:50]}")


async def get_profile():
    """Get current user profile."""
    print("\n[3] GET USER PROFILE")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_V1}/users/me", headers=headers)
            await log_result("GET", "/users/me", response.status_code)
        except Exception as e:
            await log_result("GET", "/users/me", 0, f"Error: {str(e)[:50]}")


async def test_categories():
    """Test category endpoints."""
    print("\n[4] TEST CATEGORIES")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        # Get all categories
        try:
            response = await client.get(f"{API_V1}/categories", headers=headers)
            await log_result("GET", "/categories", response.status_code)
            if response.status_code == 200:
                categories = response.json()
                if categories and isinstance(categories, list) and len(categories) > 0:
                    test_data["category_id"] = categories[0].get("id")
                    print(f"   Found {len(categories)} categories")
        except Exception as e:
            await log_result("GET", "/categories", 0, f"Error: {str(e)[:50]}")


async def test_listings():
    """Test listing endpoints."""
    print("\n[5] TEST LISTINGS")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        # Get all listings
        try:
            response = await client.get(f"{API_V1}/listings", headers=headers)
            await log_result("GET", "/listings", response.status_code)
        except Exception as e:
            await log_result("GET", "/listings", 0, f"Error: {str(e)[:50]}")

        # Create listing (if category available)
        if test_data["category_id"]:
            try:
                response = await client.post(
                    f"{API_V1}/listings",
                    headers=headers,
                    json={
                        "title": "Test iPhone",
                        "description": "Test listing",
                        "category_id": test_data["category_id"],
                        "price": 10000000,
                        "condition_grade": "like_new",
                        "location": "Hanoi"
                    }
                )
                await log_result("POST", "/listings", response.status_code)
                if response.status_code in [200, 201]:
                    test_data["listing_id"] = response.json().get("id")
            except Exception as e:
                await log_result("POST", "/listings", 0, f"Error: {str(e)[:50]}")

        # Get user listings
        try:
            response = await client.get(f"{API_V1}/listings/me", headers=headers)
            await log_result("GET", "/listings/me", response.status_code)
        except Exception as e:
            await log_result("GET", "/listings/me", 0, f"Error: {str(e)[:50]}")


async def test_offers():
    """Test offer endpoints."""
    print("\n[6] TEST OFFERS")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        # Get received offers
        try:
            response = await client.get(f"{API_V1}/offers/me/received", headers=headers)
            await log_result("GET", "/offers/me/received", response.status_code)
        except Exception as e:
            await log_result("GET", "/offers/me/received", 0, f"Error: {str(e)[:50]}")

        # Get sent offers
        try:
            response = await client.get(f"{API_V1}/offers/me/sent", headers=headers)
            await log_result("GET", "/offers/me/sent", response.status_code)
        except Exception as e:
            await log_result("GET", "/offers/me/sent", 0, f"Error: {str(e)[:50]}")


async def test_orders():
    """Test order endpoints."""
    print("\n[7] TEST ORDERS")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        # Get all orders
        try:
            response = await client.get(f"{API_V1}/orders", headers=headers)
            await log_result("GET", "/orders", response.status_code)
        except Exception as e:
            await log_result("GET", "/orders", 0, f"Error: {str(e)[:50]}")

        # Get user orders
        try:
            response = await client.get(f"{API_V1}/orders/me", headers=headers)
            await log_result("GET", "/orders/me", response.status_code)
        except Exception as e:
            await log_result("GET", "/orders/me", 0, f"Error: {str(e)[:50]}")


async def test_reviews():
    """Test review endpoints."""
    print("\n[8] TEST REVIEWS")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        # Get user reviews
        try:
            response = await client.get(f"{API_V1}/reviews/me", headers=headers)
            await log_result("GET", "/reviews/me", response.status_code)
        except Exception as e:
            await log_result("GET", "/reviews/me", 0, f"Error: {str(e)[:50]}")


async def test_users():
    """Test user endpoints."""
    print("\n[9] TEST USERS")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        if test_data["user_id"]:
            try:
                response = await client.get(
                    f"{API_V1}/users/{test_data['user_id']}",
                    headers=headers
                )
                await log_result("GET", f"/users/{test_data['user_id']}", response.status_code)
            except Exception as e:
                await log_result("GET", f"/users/{{user_id}}", 0, f"Error: {str(e)[:50]}")


async def test_auth_endpoints():
    """Test auth endpoints."""
    print("\n[10] TEST AUTH ENDPOINTS")
    headers = _get_auth_headers()
    async with httpx.AsyncClient() as client:
        # Verify email
        try:
            response = await client.post(f"{API_V1}/auth/verify-email")
            await log_result("POST", "/auth/verify-email", response.status_code)
        except Exception as e:
            await log_result("POST", "/auth/verify-email", 0, f"Error: {str(e)[:50]}")

        # Refresh token
        try:
            response = await client.post(f"{API_V1}/auth/refresh", headers=headers)
            await log_result("POST", "/auth/refresh", response.status_code)
        except Exception as e:
            await log_result("POST", "/auth/refresh", 0, f"Error: {str(e)[:50]}")

        # Logout
        try:
            response = await client.post(f"{API_V1}/auth/logout", headers=headers)
            await log_result("POST", "/auth/logout", response.status_code)
        except Exception as e:
            await log_result("POST", "/auth/logout", 0, f"Error: {str(e)[:50]}")


def _get_auth_headers():
    """Get authorization headers if token exists."""
    if test_data["access_token"]:
        return {"Authorization": f"Bearer {test_data['access_token']}"}
    return {}


async def print_summary():
    """Print test summary."""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    success = len(results.get(2, []))
    redirect = len(results.get(3, []))
    client_error = len(results.get(4, []))
    server_error = len(results.get(5, []))

    print(f"\nSUCCESS (2xx):        {success}")
    print(f"REDIRECT (3xx):      {redirect}")
    print(f"CLIENT ERROR (4xx):   {client_error}")
    print(f"SERVER ERROR (5xx):   {server_error}")
    print(
        f"\nTOTAL:               {success + redirect + client_error + server_error}")

    if client_error > 0:
        print(f"\nClient Errors (4xx):")
        for item in results.get(4, []):
            print(
                f"   {item['method']:6} {item['path']:50} -> {item['status']}")

    if server_error > 0:
        print(f"\nServer Errors (5xx):")
        for item in results.get(5, []):
            print(
                f"   {item['method']:6} {item['path']:50} -> {item['status']}")

    print("\n" + "=" * 80)


async def main():
    """Run all tests."""
    print("=" * 80)
    print(f"TEST SUITE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    await register_user()
    await login_user()
    await get_profile()
    await test_categories()
    await test_listings()
    await test_offers()
    await test_orders()
    await test_reviews()
    await test_users()
    await test_auth_endpoints()

    await print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
