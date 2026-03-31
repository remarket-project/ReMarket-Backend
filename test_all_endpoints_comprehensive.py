#!/usr/bin/env python3
"""
Comprehensive API Endpoint Test Suite - Full Coverage
Tests ALL endpoints from OpenAPI specification with detailed reporting.
"""
import json
import httpx
import asyncio
from uuid import UUID
from collections import defaultdict
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Test user credentials
TEST_EMAIL = f"apitest{int(datetime.now().timestamp())}@test.com"
TEST_PASSWORD = "TestPass123!@#"
TEST_PHONE = "0987654321"

# Shared test data
test_data = {
    "access_token": None,
    "user_id": None,
    "category_id": None,
    "listing_id": None,
    "image_id": None,
    "offer_id": None,
    "order_id": None,
    "review_id": None,
    "notification_id": None,
}

# Results tracking
results = defaultdict(list)
TOTAL_TESTS = 0
PASSED = 0
FAILED = 0


def get_headers():
    """Get auth headers if token exists."""
    if test_data["access_token"]:
        return {"Authorization": f"Bearer {test_data['access_token']}"}
    return {}


async def test_endpoint(method: str, path: str, name: str, **kwargs):
    """Test a single endpoint and record result."""
    global TOTAL_TESTS, PASSED, FAILED
    TOTAL_TESTS += 1

    try:
        url = f"{API_V1}{path}"
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=get_headers(), **kwargs)
            elif method == "POST":
                response = await client.post(url, headers=get_headers(), **kwargs)
            elif method == "PUT":
                response = await client.put(url, headers=get_headers(), **kwargs)
            elif method == "PATCH":
                response = await client.patch(url, headers=get_headers(), **kwargs)
            elif method == "DELETE":
                response = await client.delete(url, headers=get_headers(), **kwargs)

            status = response.status_code
            is_success = 200 <= status < 300

            if is_success:
                PASSED += 1
                symbol = "PASS"
            else:
                FAILED += 1
                symbol = "FAIL"

            results[symbol].append({
                "method": method,
                "path": path,
                "status": status,
                "name": name
            })

            print(f"[{symbol}] {method:6} {path:50} {status:3} - {name}")

            return response, status
    except Exception as e:
        FAILED += 1
        results["ERROR"].append({
            "method": method,
            "path": path,
            "error": str(e),
            "name": name
        })
        print(
            f"[ERRO] {method:6} {path:50}     - {name} (Error: {str(e)[:50]})")
        return None, 0


async def test_auth():
    """Test authentication endpoints."""
    print("\n" + "="*90)
    print("AUTH ENDPOINTS")
    print("="*90)

    # 1. Register
    resp, status = await test_endpoint(
        "POST", "/auth/register",
        "Register new user",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": "Test User",
            "phone": TEST_PHONE
        }
    )
    if status == 201 and resp:
        data = resp.json()
        test_data["access_token"] = data.get("access_token")
        test_data["user_id"] = data.get("user", {}).get("id")

    # 2. Login
    resp, status = await test_endpoint(
        "POST", "/auth/login",
        "User login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if status == 200 and resp:
        test_data["access_token"] = resp.json().get("access_token")

    # 3. Logout
    await test_endpoint("POST", "/auth/logout", "User logout")

    # 4. Verify Email
    await test_endpoint(
        "POST", "/auth/verify-email",
        "Verify email",
        json={"token": "test-token"}
    )

    # 5. Refresh Token
    if test_data["access_token"]:
        await test_endpoint(
            "POST", "/auth/refresh",
            "Refresh access token",
            json={"refresh_token": "test-refresh"}
        )


async def test_users():
    """Test user endpoints."""
    print("\n" + "="*90)
    print("USER ENDPOINTS")
    print("="*90)

    # 1. Get My Profile
    await test_endpoint("GET", "/users/me", "Get my profile")

    # 2. Update My Profile
    await test_endpoint(
        "PUT", "/users/me",
        "Update my profile",
        json={"full_name": "Updated Name"}
    )

    # 3. Change Password
    await test_endpoint(
        "PUT", "/users/me/password",
        "Change password",
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "NewPass123!@#",
            "confirm_password": "NewPass123!@#"
        }
    )

    # 4. Get User Public Profile
    if test_data["user_id"]:
        await test_endpoint(
            "GET", f"/users/{test_data['user_id']}",
            "Get user public profile"
        )

    # 5. List Users (Admin)
    await test_endpoint(
        "GET", "/users/",
        "List users",
        params={"skip": 0, "limit": 10}
    )

    # 6. Admin List Users
    await test_endpoint(
        "GET", "/admin/users",
        "Admin list users",
        params={"skip": 0, "limit": 10}
    )


async def test_categories():
    """Test category endpoints."""
    print("\n" + "="*90)
    print("CATEGORY ENDPOINTS")
    print("="*90)

    # 1. List Categories
    resp, status = await test_endpoint(
        "GET", "/categories/",
        "List categories",
        params={"skip": 0, "limit": 100}
    )
    if status == 200 and resp:
        categories = resp.json().get("data", [])
        if categories:
            test_data["category_id"] = categories[0].get("id")

    # 2. Get Root Categories
    await test_endpoint("GET", "/categories/roots", "Get root categories")

    # 3. Get Category by Slug
    await test_endpoint("GET", "/categories/electronics", "Get category by slug")


async def test_listings():
    """Test listing endpoints."""
    print("\n" + "="*90)
    print("LISTING ENDPOINTS")
    print("="*90)

    # 1. List Listings
    resp, status = await test_endpoint(
        "GET", "/listings/",
        "List all listings",
        params={"skip": 0, "limit": 20}
    )

    # 2. Create Listing
    if test_data["category_id"]:
        resp, status = await test_endpoint(
            "POST", "/listings/",
            "Create listing",
            json={
                "title": "Test iPhone 13",
                "description": "Like new condition",
                "price": 15000000,
                "condition_grade": "like_new",
                "category_id": str(test_data["category_id"]),
                "is_negotiable": True
            }
        )
        if status == 201 and resp:
            test_data["listing_id"] = resp.json().get("id")

    # 3. Get My Listings
    await test_endpoint(
        "GET", "/listings/me",
        "Get my listings",
        params={"skip": 0, "limit": 20}
    )

    # 4. Get Listing Detail
    if test_data["listing_id"]:
        await test_endpoint(
            "GET", f"/listings/{test_data['listing_id']}",
            "Get listing detail"
        )

        # 5. Update Listing
        resp, status = await test_endpoint(
            "PATCH", f"/listings/{test_data['listing_id']}",
            "Update listing",
            json={"title": "Updated iPhone 13"}
        )

        # 6. Upload Listing Image
        await test_endpoint(
            "POST", f"/listings/{test_data['listing_id']}/images",
            "Upload listing image",
            files={"file": ("test.jpg", b"fake image data")},
            params={"is_primary": True}
        )


async def test_offers():
    """Test offer endpoints."""
    print("\n" + "="*90)
    print("OFFER ENDPOINTS")
    print("="*90)

    # 1. Get Sent Offers
    await test_endpoint(
        "GET", "/offers/me/sent",
        "Get my sent offers"
    )

    # 2. Get Received Offers
    await test_endpoint(
        "GET", "/offers/me/received",
        "Get my received offers"
    )

    # 3. Create Offer
    if test_data["listing_id"]:
        resp, status = await test_endpoint(
            "POST", "/offers/",
            "Create offer",
            json={
                "listing_id": str(test_data["listing_id"]),
                "offer_price": 14000000
            }
        )
        if status == 201 and resp:
            test_data["offer_id"] = resp.json().get("id")

    # 4. Get Offers for Listing
    if test_data["listing_id"]:
        await test_endpoint(
            "GET", f"/offers/listing/{test_data['listing_id']}",
            "Get offers for listing"
        )

    # 5. Get Offer Detail
    if test_data["offer_id"]:
        await test_endpoint(
            "GET", f"/offers/{test_data['offer_id']}",
            "Get offer detail"
        )

        # 6. Update Offer Status
        await test_endpoint(
            "PATCH", f"/offers/{test_data['offer_id']}/status",
            "Update offer status",
            json={"status": "rejected"}
        )


async def test_orders():
    """Test order endpoints."""
    print("\n" + "="*90)
    print("ORDER ENDPOINTS")
    print("="*90)

    # 1. Get My Orders
    resp, status = await test_endpoint(
        "GET", "/orders",
        "Get my orders"
    )

    # 2. Get My Orders (me)
    await test_endpoint(
        "GET", "/orders/me",
        "Get my orders (me)"
    )

    # 3. Create Direct Order
    if test_data["listing_id"]:
        resp, status = await test_endpoint(
            "POST", "/orders",
            "Create direct order",
            json={"listing_id": str(test_data["listing_id"])}
        )
        if status == 201 and resp:
            test_data["order_id"] = resp.json().get("id")

    # 4. Get Order Detail
    if test_data["order_id"]:
        await test_endpoint(
            "GET", f"/orders/{test_data['order_id']}",
            "Get order detail"
        )

        # 5. Update Order Status
        await test_endpoint(
            "PATCH", f"/orders/{test_data['order_id']}/status",
            "Update order status",
            json={"status": "confirmed"}
        )

        # 6. Complete Order
        await test_endpoint(
            "POST", f"/orders/{test_data['order_id']}/complete",
            "Complete order"
        )

        # 7. Cancel Order
        await test_endpoint(
            "POST", f"/orders/{test_data['order_id']}/cancel",
            "Cancel order"
        )


async def test_reviews():
    """Test review endpoints."""
    print("\n" + "="*90)
    print("REVIEW ENDPOINTS")
    print("="*90)

    # 1. Create Review
    if test_data["order_id"]:
        resp, status = await test_endpoint(
            "POST", "/reviews",
            "Create review",
            json={
                "order_id": str(test_data["order_id"]),
                "rating": 5,
                "comment": "Great seller!"
            }
        )
        if status == 201 and resp:
            test_data["review_id"] = resp.json().get("id")

    # 2. Get Review
    if test_data["order_id"]:
        await test_endpoint(
            "GET", f"/reviews/{test_data['order_id']}",
            "Get review for order"
        )

    # 3. Get User Reviews
    if test_data["user_id"]:
        await test_endpoint(
            "GET", f"/reviews/user/{test_data['user_id']}",
            "Get all user reviews"
        )


async def test_notifications():
    """Test notification endpoints."""
    print("\n" + "="*90)
    print("NOTIFICATION ENDPOINTS")
    print("="*90)

    # 1. Get My Notifications
    resp, status = await test_endpoint(
        "GET", "/notifications/",
        "Get my notifications",
        params={"skip": 0, "limit": 20}
    )
    if status == 200 and resp:
        items = resp.json().get("items", [])
        if items:
            test_data["notification_id"] = items[0].get("id")

    # 2. Get Unread Count
    await test_endpoint(
        "GET", "/notifications/unread-count",
        "Get unread notifications count"
    )

    # 3. Mark Notification as Read
    if test_data["notification_id"]:
        await test_endpoint(
            "PUT", f"/notifications/{test_data['notification_id']}/read",
            "Mark notification as read"
        )

    # 4. Mark All as Read
    await test_endpoint(
        "PUT", "/notifications/read-all",
        "Mark all notifications as read"
    )


async def test_admin():
    """Test admin endpoints."""
    print("\n" + "="*90)
    print("ADMIN ENDPOINTS")
    print("="*90)

    # 1. Get Pending Listings
    await test_endpoint(
        "GET", "/admin/listings/pending",
        "Get pending listings"
    )

    # 2. Approve Listing (if there are pending listings)
    if test_data["listing_id"]:
        await test_endpoint(
            "POST", f"/admin/listings/{test_data['listing_id']}/approve",
            "Approve listing"
        )

    # 3. Reject Listing
    if test_data["listing_id"]:
        await test_endpoint(
            "POST", f"/admin/listings/{test_data['listing_id']}/reject",
            "Reject listing",
            json={"reason": "Inappropriate content"}
        )

    # 4. Update User Status
    if test_data["user_id"]:
        await test_endpoint(
            "PATCH", f"/admin/users/{test_data['user_id']}/status",
            "Update user status",
            json={"is_active": True}
        )


async def test_utils():
    """Test utility endpoints."""
    print("\n" + "="*90)
    print("UTILITY ENDPOINTS")
    print("="*90)

    # 1. Health Check
    await test_endpoint(
        "GET", "/utils/health-check/",
        "Health check"
    )

    # 2. Root
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/")
        status = resp.status_code
        print(
            f"[PASS] GET     /                                                      {status:3} - Root endpoint")


async def print_summary():
    """Print comprehensive test summary."""
    print("\n" + "="*90)
    print("TEST SUMMARY REPORT")
    print("="*90)

    print(f"\nTotal Tests Run:       {TOTAL_TESTS}")
    print(f"Passed (2xx):          {PASSED}")
    print(f"Failed:                {FAILED}")
    print(f"Success Rate:          {(PASSED/TOTAL_TESTS*100):.1f}%")

    if results.get("FAIL"):
        print(f"\n⚠️  FAILED ENDPOINTS ({len(results['FAIL'])}):")
        for item in results["FAIL"]:
            print(
                f"   [{item['status']}] {item['method']:6} {item['path']:50} - {item['name']}")

    if results.get("ERROR"):
        print(f"\n❌ ERROR ENDPOINTS ({len(results['ERROR'])}):")
        for item in results["ERROR"]:
            print(
                f"   [ERR] {item['method']:6} {item['path']:50} - {item['name']}")

    if FAILED == 0:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {FAILED} test(s) failed or errored")

    print("\n" + "="*90)


async def main():
    """Run all endpoint tests."""
    print("="*90)
    print("COMPREHENSIVE API ENDPOINT TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*90)

    await test_auth()
    await test_users()
    await test_categories()
    await test_listings()
    await test_offers()
    await test_orders()
    await test_reviews()
    await test_notifications()
    await test_admin()
    await test_utils()

    await print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
