#!/usr/bin/env python3
"""Test all fixed endpoints - simplified version"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"


async def test_endpoints():
    """Test all key endpoints"""
    results = {
        "passed": [],
        "failed": []
    }

    async with httpx.AsyncClient(timeout=10) as client:
        # Admin login - use existing admin for testing
        admin_email = "admin@example.com"
        admin_password = "Admin@123456"

        print("🔹 Testing Admin Login...")
        try:
            resp = await client.post(
                f"{BASE_URL}/auth/login",
                json={"email": admin_email, "password": admin_password}
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                print(f"✅ Login successful - {resp.status_code}")
            else:
                print(f"⚠️ Admin login failed: {resp.status_code}")
                return results
        except Exception as e:
            print(f"❌ Login error: {e}")
            return results

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Test GET /users/me
        print("🔹 Testing GET /users/me...")
        try:
            resp = await client.get(f"{BASE_URL}/users/me", headers=headers)
            if resp.status_code == 200:
                print(f"✅ GET /users/me - {resp.status_code}")
                results["passed"].append("GET /users/me")
            else:
                print(
                    f"❌ GET /users/me - {resp.status_code}: {resp.text[:200]}")
                results["failed"].append(f"GET /users/me ({resp.status_code})")
        except Exception as e:
            print(f"❌ GET /users/me - Error: {e}")
            results["failed"].append(f"GET /users/me (Error)")

        # 2. Test PUT /users/me (FIXED)
        print("🔹 Testing PUT /users/me...")
        try:
            resp = await client.put(
                f"{BASE_URL}/users/me",
                headers=headers,
                json={
                    "full_name": "Admin Updated",
                    "phone": "0987654321"
                }
            )
            if resp.status_code == 200:
                print(f"✅ PUT /users/me - {resp.status_code}")
                results["passed"].append("PUT /users/me")
            else:
                print(
                    f"❌ PUT /users/me - {resp.status_code}: {resp.text[:200]}")
                results["failed"].append(f"PUT /users/me ({resp.status_code})")
        except Exception as e:
            print(f"❌ PUT /users/me - Error: {e}")
            results["failed"].append(f"PUT /users/me (Error)")

        # 3. Test GET /categories/roots
        print("🔹 Testing GET /categories/roots...")
        try:
            resp = await client.get(f"{BASE_URL}/categories/roots")
            if resp.status_code == 200:
                cats = resp.json()
                if cats and len(cats) > 0:
                    category_id = cats[0]["id"]
                    print(f"✅ GET /categories/roots - {resp.status_code}")
                    results["passed"].append("GET /categories/roots")
                else:
                    print(f"⚠️ No categories found")
                    category_id = None
            else:
                print(f"❌ GET /categories/roots - {resp.status_code}")
                results["failed"].append(
                    f"GET /categories/roots ({resp.status_code})")
                category_id = None
        except Exception as e:
            print(f"❌ GET /categories/roots - Error: {e}")
            results["failed"].append(f"GET /categories/roots (Error)")
            category_id = None

        # 4. Test POST /listings/ (FIXED)
        if category_id:
            print("🔹 Testing POST /listings/...")
            try:
                resp = await client.post(
                    f"{BASE_URL}/listings/",
                    headers=headers,
                    json={
                        "title": f"Test Listing {datetime.now().timestamp():.0f}",
                        "description": "A test listing",
                        "price": 100.00,
                        "is_negotiable": True,
                        "condition_grade": "NEW",
                        "category_id": category_id
                    }
                )
                if resp.status_code == 201:
                    listing = resp.json()
                    print(f"✅ POST /listings/ - {resp.status_code}")
                    results["passed"].append("POST /listings/")
                else:
                    print(
                        f"❌ POST /listings/ - {resp.status_code}: {resp.text[:200]}")
                    results["failed"].append(
                        f"POST /listings/ ({resp.status_code})")
            except Exception as e:
                print(f"❌ POST /listings/ - Error: {e}")
                results["failed"].append(f"POST /listings/ (Error)")

        # 5. Test GET /listings/me
        print("🔹 Testing GET /listings/me...")
        try:
            resp = await client.get(f"{BASE_URL}/listings/me", headers=headers)
            if resp.status_code == 200:
                print(f"✅ GET /listings/me - {resp.status_code}")
                results["passed"].append("GET /listings/me")
            else:
                print(f"❌ GET /listings/me - {resp.status_code}")
                results["failed"].append(
                    f"GET /listings/me ({resp.status_code})")
        except Exception as e:
            print(f"❌ GET /listings/me - Error: {e}")
            results["failed"].append(f"GET /listings/me (Error)")

        # 6. Test GET /notifications/ (FIXED)
        print("🔹 Testing GET /notifications/...")
        try:
            resp = await client.get(f"{BASE_URL}/notifications/", headers=headers)
            if resp.status_code == 200:
                print(f"✅ GET /notifications/ - {resp.status_code}")
                results["passed"].append("GET /notifications/")
            else:
                print(
                    f"❌ GET /notifications/ - {resp.status_code}: {resp.text[:200]}")
                results["failed"].append(
                    f"GET /notifications/ ({resp.status_code})")
        except Exception as e:
            print(f"❌ GET /notifications/ - Error: {e}")
            results["failed"].append(f"GET /notifications/ (Error)")

        # 7. Test GET /notifications/unread-count
        print("🔹 Testing GET /notifications/unread-count...")
        try:
            resp = await client.get(f"{BASE_URL}/notifications/unread-count", headers=headers)
            if resp.status_code == 200:
                print(
                    f"✅ GET /notifications/unread-count - {resp.status_code}")
                results["passed"].append("GET /notifications/unread-count")
            else:
                print(
                    f"❌ GET /notifications/unread-count - {resp.status_code}")
                results["failed"].append(
                    f"GET /notifications/unread-count ({resp.status_code})")
        except Exception as e:
            print(f"❌ GET /notifications/unread-count - Error: {e}")
            results["failed"].append(
                f"GET /notifications/unread-count (Error)")

        # 8. Test GET /reviews/user/{user_id} (FIXED)
        # Use a dummy UUID first to see if endpoint works
        dummy_user_id = "00000000-0000-0000-0000-000000000001"
        print(f"🔹 Testing GET /reviews/user/{{user_id}}...")
        try:
            resp = await client.get(f"{BASE_URL}/reviews/user/{dummy_user_id}", headers=headers)
            if resp.status_code == 200:
                print(f"✅ GET /reviews/user/{{user_id}} - {resp.status_code}")
                results["passed"].append("GET /reviews/user/{user_id}")
            else:
                print(f"❌ GET /reviews/user/{{user_id}} - {resp.status_code}")
                results["failed"].append(
                    f"GET /reviews/user/{{user_id}} ({resp.status_code})")
        except Exception as e:
            print(f"❌ GET /reviews/user/{{user_id}} - Error: {e}")
            results["failed"].append(f"GET /reviews/user/{{user_id}} (Error)")

    return results

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Fixed Endpoints")
    print("=" * 60)
    print()
    results = asyncio.run(test_endpoints())
    print()
    print("=" * 60)
    print(
        f"SUMMARY: {len(results['passed'])} passed, {len(results['failed'])} failed")
    print("=" * 60)
    print(f"\n✅ Passed ({len(results['passed'])}): {results['passed']}")
    print(f"\n❌ Failed ({len(results['failed'])}): {results['failed']}")
