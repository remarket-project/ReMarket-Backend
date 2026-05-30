"""Tests for admin audit trail endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import User
from app.models.enums import ListingStatus
from tests.utils.admin_helper import (
    create_test_category,
    create_test_listing,
    create_test_user,
)
from tests.utils.user import authentication_token_from_email_async

pytestmark = pytest.mark.asyncio


class TestAdminAuditTrail:
    """GET /admin/audit-trail"""

    async def test_audit_trail_empty(
        self,
        client: TestClient,
        admin_token_headers: dict,
    ):
        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    async def test_audit_log_after_approve_listing(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.PENDING
        )

        resp = client.post(
            f"{settings.API_V1_STR}/admin/listings/{listing.id}/approve",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200

        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        items = data["items"]

        approve_logs = [
            item
            for item in items
            if item["action"] == "listing_approved"
            and item["target_id"] == str(listing.id)
        ]
        assert len(approve_logs) >= 1, (
            f"Không tìm thấy audit log cho listing {listing.id}"
        )

    async def test_audit_log_after_reject_listing(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.PENDING
        )

        resp = client.post(
            f"{settings.API_V1_STR}/admin/listings/{listing.id}/reject",
            headers=admin_token_headers,
            json={"reason": "Test reject"},
        )
        assert resp.status_code == 200

        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        reject_logs = [
            item
            for item in data["items"]
            if item["action"] == "listing_rejected"
            and item["target_id"] == str(listing.id)
        ]
        assert len(reject_logs) >= 1

    async def test_audit_log_after_update_user_status(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        target_user = await create_test_user(async_db, is_admin=False)

        resp = client.patch(
            f"{settings.API_V1_STR}/admin/users/{target_user.id}/status",
            headers=admin_token_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 200

        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        user_logs = [
            item
            for item in data["items"]
            if item["action"] == "user_status_updated"
            and item["target_id"] == str(target_user.id)
        ]
        assert len(user_logs) >= 1
        assert any(
            "is_active=False" in (log.get("note") or "") for log in user_logs
        )

    async def test_filter_by_action(
        self,
        client: TestClient,
        admin_token_headers: dict,
    ):
        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail?action=listing_approved",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["action"] == "listing_approved"

    async def test_filter_by_target_type(
        self,
        client: TestClient,
        admin_token_headers: dict,
    ):
        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail?target_type=user",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["target_type"] == "user"

    async def test_pagination(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)

        for _ in range(2):
            listing = await create_test_listing(
                async_db,
                seller.id,
                category.id,
                status=ListingStatus.PENDING,
            )
            resp = client.post(
                f"{settings.API_V1_STR}/admin/listings/{listing.id}/approve",
                headers=admin_token_headers,
            )
            assert resp.status_code == 200

        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail?skip=0&limit=1",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 1
        assert data["limit"] == 1
        assert data["skip"] == 0

    async def test_forbidden_for_normal_user(
        self,
        client: TestClient,
        async_db: AsyncSession,
    ):
        user = await create_test_user(async_db, is_admin=False)
        token_headers = await authentication_token_from_email_async(
            client, user.email, async_db
        )
        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail",
            headers=token_headers,
        )
        assert resp.status_code == 403

    async def test_audit_log_structure(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.PENDING
        )
        resp = client.post(
            f"{settings.API_V1_STR}/admin/listings/{listing.id}/approve",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200

        resp = client.get(
            f"{settings.API_V1_STR}/admin/audit-trail",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "admin_id" in item
            assert "action" in item
            assert "created_at" in item
            assert "target_type" in item
            assert "target_id" in item
            assert "note" in item
