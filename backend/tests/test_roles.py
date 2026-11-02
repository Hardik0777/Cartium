"""Role guards, tested through a small throwaway router so they're checked independently of later features."""
from fastapi import APIRouter, Depends

from app.dependencies.auth import require_approved_seller, require_role
from app.main import app
from app.models import Role, SellerStatus

probe = APIRouter(prefix="/_test")


@probe.get("/admin")
def admin_only(user=Depends(require_role(Role.admin))):
    return {"ok": user.email}


@probe.get("/seller")
def seller_only(user=Depends(require_approved_seller)):
    return {"ok": user.email}


app.include_router(probe)


def test_admin_route_blocks_other_roles(client, make_user, login):
    make_user(email="a@test.dev", role=Role.admin)
    make_user(email="b@test.dev", role=Role.buyer)
    assert client.get("/_test/admin", headers=login("a@test.dev")).status_code == 200
    assert client.get("/_test/admin", headers=login("b@test.dev")).status_code == 403


def test_pending_seller_is_blocked_until_approved(client, make_user, login):
    make_user(email="new@test.dev", role=Role.seller, seller_status=SellerStatus.pending)
    make_user(email="ok@test.dev", role=Role.seller, seller_status=SellerStatus.approved)
    pending = client.get("/_test/seller", headers=login("new@test.dev"))
    assert pending.status_code == 403 and "approval" in pending.json()["detail"]
    assert client.get("/_test/seller", headers=login("ok@test.dev")).status_code == 200
