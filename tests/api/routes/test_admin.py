"""Tests for admin API endpoints."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Order, User
from app.models.enums import EscrowStatus, ListingStatus, OrderStatus
from tests.utils.admin_helper import (
    create_test_category,
    create_test_listing,
    create_test_order_and_escrow,
    create_test_user,
    create_test_wallet,
)
from tests.utils.user import authentication_token_from_email_async

pytestmark = pytest.mark.asyncio


class TestAdminDashboard:
    """GET /admin/dashboard"""

    async def test_success(
        self, client: TestClient, admin_token_headers: dict
    ):
        resp = client.get(
            f"{settings.API_V1_STR}/admin/dashboard",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_listings" in data
        assert "total_orders" in data
        assert "disputed_escrows" in data

    async def test_forbidden_for_normal_user(
        self, client: TestClient, async_db: AsyncSession
    ):
        user = await create_test_user(async_db, is_admin=False)
        token_headers = await authentication_token_from_email_async(
            client, user.email, async_db
        )
        resp = client.get(
            f"{settings.API_V1_STR}/admin/dashboard",
            headers=token_headers,
        )
        assert resp.status_code == 403

    async def test_unauthorized(self, client: TestClient):
        resp = client.get(
            f"{settings.API_V1_STR}/admin/dashboard",
        )
        assert resp.status_code == 403


class TestAdminListUsers:
    """GET /admin/users"""

    async def test_list_users(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        await create_test_user(async_db)

        resp = client.get(
            f"{settings.API_V1_STR}/admin/users",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 1

    async def test_pagination(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        for _ in range(3):
            await create_test_user(async_db)

        resp = client.get(
            f"{settings.API_V1_STR}/admin/users?skip=0&limit=2",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 2


class TestAdminUpdateUserStatus:
    """PATCH /admin/users/{user_id}/status"""

    async def test_lock_user(
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
        data = resp.json()
        assert data["is_active"] is False
        assert data["id"] == str(target_user.id)

    async def test_unlock_user(
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

        resp = client.patch(
            f"{settings.API_V1_STR}/admin/users/{target_user.id}/status",
            headers=admin_token_headers,
            json={"is_active": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    async def test_cannot_lock_self(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
        admin_user: User,
    ):
        resp = client.patch(
            f"{settings.API_V1_STR}/admin/users/{admin_user.id}/status",
            headers=admin_token_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 400
        assert "chính mình" in resp.json()["detail"]

    async def test_user_not_found(
        self, client: TestClient, admin_token_headers: dict
    ):
        resp = client.patch(
            f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}/status",
            headers=admin_token_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 404
        assert "không tìm thấy" in resp.json()["detail"]


class TestAdminPendingListings:
    """GET /admin/listings/pending"""

    async def test_list_pending(
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

        resp = client.get(
            f"{settings.API_V1_STR}/admin/listings/pending",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        listings = resp.json()
        assert len(listings) >= 1
        listing_ids = [l["id"] for l in listings]
        assert str(listing.id) in listing_ids

    async def test_empty_when_no_pending(
        self, client: TestClient, admin_token_headers: dict
    ):
        resp = client.get(
            f"{settings.API_V1_STR}/admin/listings/pending",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_hides_active_listings(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.ACTIVE
        )

        resp = client.get(
            f"{settings.API_V1_STR}/admin/listings/pending",
            headers=admin_token_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestAdminApproveListing:
    """POST /admin/listings/{listing_id}/approve"""

    async def test_approve_success(
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
        data = resp.json()
        assert data["status"] == ListingStatus.ACTIVE.value
        assert data["id"] == str(listing.id)

    async def test_approve_already_active_fails(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.ACTIVE
        )

        resp = client.post(
            f"{settings.API_V1_STR}/admin/listings/{listing.id}/approve",
            headers=admin_token_headers,
        )
        assert resp.status_code == 400
        assert "PENDING" in resp.json()["detail"]

    async def test_approve_not_found(
        self, client: TestClient, admin_token_headers: dict
    ):
        resp = client.post(
            f"{settings.API_V1_STR}/admin/listings/{uuid.uuid4()}/approve",
            headers=admin_token_headers,
        )
        assert resp.status_code == 404
        assert "không tìm thấy" in resp.json()["detail"]


class TestAdminRejectListing:
    """POST /admin/listings/{listing_id}/reject"""

    async def test_reject_with_reason(
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
            json={"reason": "Ảnh không rõ ràng, vui lòng đăng lại"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == ListingStatus.REJECTED.value
        assert (
            data["rejection_reason"]
            == "Ảnh không rõ ràng, vui lòng đăng lại"
        )

    async def test_reject_without_reason(
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
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == ListingStatus.REJECTED.value

    async def test_reject_non_pending_fails(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.SOLD
        )

        resp = client.post(
            f"{settings.API_V1_STR}/admin/listings/{listing.id}/reject",
            headers=admin_token_headers,
            json={"reason": "test"},
        )
        assert resp.status_code == 400
        assert "PENDING" in resp.json()["detail"]


class TestAdminResolveEscrow:
    """POST /admin/escrows/{order_id}/resolve"""

    async def test_resolve_release_to_seller(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        buyer = await create_test_user(async_db)
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db,
            seller.id,
            category.id,
            status=ListingStatus.ACTIVE,
            price=Decimal("500000.00"),
        )
        await create_test_wallet(async_db, buyer.id, balance=Decimal("1000000.00"))
        await create_test_wallet(async_db, seller.id, balance=Decimal("0.00"))

        order, escrow = await create_test_order_and_escrow(
            async_db,
            buyer,
            seller,
            listing,
            escrow_status=EscrowStatus.DISPUTED,
        )

        resp = client.post(
            f"{settings.API_V1_STR}/admin/escrows/{order.id}/resolve",
            headers=admin_token_headers,
            json={
                "result": "release",
                "note": "Admin resolves in favor of seller",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "release"
        assert data["order_id"] == str(order.id)

    async def test_resolve_refund_buyer(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        buyer = await create_test_user(async_db)
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db,
            seller.id,
            category.id,
            status=ListingStatus.ACTIVE,
            price=Decimal("300000.00"),
        )
        await create_test_wallet(async_db, buyer.id, balance=Decimal("800000.00"))
        await create_test_wallet(async_db, seller.id, balance=Decimal("0.00"))

        order, escrow = await create_test_order_and_escrow(
            async_db,
            buyer,
            seller,
            listing,
            escrow_status=EscrowStatus.DISPUTED,
        )

        resp = client.post(
            f"{settings.API_V1_STR}/admin/escrows/{order.id}/resolve",
            headers=admin_token_headers,
            json={"result": "refund", "note": "Admin refunds buyer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "refund"

    async def test_resolve_order_not_found(
        self, client: TestClient, admin_token_headers: dict
    ):
        resp = client.post(
            f"{settings.API_V1_STR}/admin/escrows/{uuid.uuid4()}/resolve",
            headers=admin_token_headers,
            json={"result": "release"},
        )
        assert resp.status_code == 404
        assert "không tìm thấy" in resp.json()["detail"]

    async def test_resolve_nonexistent_escrow(
        self,
        client: TestClient,
        admin_token_headers: dict,
        async_db: AsyncSession,
    ):
        buyer = await create_test_user(async_db)
        seller = await create_test_user(async_db)
        category = await create_test_category(async_db)
        listing = await create_test_listing(
            async_db, seller.id, category.id, status=ListingStatus.ACTIVE
        )
        order = Order(
            buyer_id=buyer.id,
            seller_id=seller.id,
            listing_id=listing.id,
            final_price=Decimal("100000.00"),
            status=OrderStatus.PENDING,
        )
        async_db.add(order)
        await async_db.commit()
        await async_db.refresh(order)

        resp = client.post(
            f"{settings.API_V1_STR}/admin/escrows/{order.id}/resolve",
            headers=admin_token_headers,
            json={"result": "release"},
        )
        assert resp.status_code == 404
        assert "Escrow không tìm thấy" in resp.json()["detail"]
