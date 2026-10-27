import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from platform_api.app import passwords
from platform_api.database import Booking, Membership, Reservation, Service, Slot, User
from platform_api.worker import run_once
from sqlalchemy import select
from test_foundation import auth


def booking_seed(app):
    with app.state.sessions.begin() as db:
        db.add(Service(id="repair", project_id="cedar", name="Repair consultation"))
        db.flush()
        for n in range(3):
            db.add(
                Slot(
                    id=f"slot-{n}",
                    service_id="repair",
                    start_at=int(time.time()) + 7200 + n * 3600,
                    end_at=int(time.time()) + 9000 + n * 3600,
                )
            )
        db.add(
            User(
                id="second",
                email="second@example.test",
                password_hash=passwords.hash("a-long-test-password"),
            )
        )
        db.flush()
        db.add(Membership(user_id="second", organization_id="cedar", role="end_user"))


def proposal(client, headers, slot="slot-0", key="test-key-1", kind="book", booking=""):
    r = client.post(
        "/v1/projects/cedar/operations",
        headers=headers,
        json={"kind": kind, "slot_id": slot, "booking_id": booking, "idempotency_key": key},
    )
    assert r.status_code == 201, r.text
    return r.json()


def confirm(client, headers, op):
    r = client.post(f"/v1/projects/cedar/operations/{op['id']}/confirm", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_booking_confirmation_idempotency_ownership_and_reminder(setup):
    client, app = setup
    booking_seed(app)
    h, other = auth(client), auth(client, "second")
    op = proposal(client, h)
    assert op["state"] == "awaiting_confirmation"
    assert client.get("/v1/projects/cedar/bookings", headers=h).json()["items"] == []
    result = confirm(client, h, op)
    assert result["state"] == "succeeded"
    assert confirm(client, h, op)["booking_id"] == result["booking_id"]
    assert proposal(client, h)["booking_id"] == result["booking_id"]
    assert client.get("/v1/projects/cedar/bookings", headers=other).json()["items"] == []
    denied = client.post(
        "/v1/projects/cedar/operations",
        headers=other,
        json={
            "kind": "cancel",
            "booking_id": result["booking_id"],
            "idempotency_key": "other-user-1",
        },
    )
    assert denied.status_code == 404
    run_once(app.state.sessions)
    assert len(client.get("/v1/projects/cedar/inbox", headers=h).json()["items"]) == 1
    run_once(app.state.sessions)
    assert len(client.get("/v1/projects/cedar/inbox", headers=h).json()["items"]) == 1
    cancellation = proposal(
        client, h, slot="", key="cancel-key-1", kind="cancel", booking=result["booking_id"]
    )
    assert confirm(client, h, cancellation)["state"] == "succeeded"
    assert (
        client.get("/v1/projects/cedar/bookings", headers=h).json()["items"][0]["status"]
        == "cancelled"
    )


def test_competing_last_slot_and_reschedule_rollback(setup):
    client, app = setup
    booking_seed(app)
    h, other = auth(client), auth(client, "second")
    first, second = proposal(client, h), proposal(client, other)

    def commit(pair):
        headers, op = pair
        with TestClient(app) as parallel:
            return confirm(parallel, headers, op)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(commit, [(h, first), (other, second)]))
    assert sorted(r["state"] for r in results) == ["failed", "succeeded"]
    with app.state.sessions() as db:
        assert len(db.scalars(select(Reservation)).all()) == 1
        assert len(db.scalars(select(Booking)).all()) == 1
    winner = 0 if results[0]["state"] == "succeeded" else 1
    wh, lh = (h, other) if winner == 0 else (other, h)
    winning_booking = results[winner]["booking_id"]
    move = proposal(client, wh, "slot-1", "move-key-1", "reschedule", winning_booking)
    rival = proposal(client, lh, "slot-1", "rival-key-1")
    assert confirm(client, lh, rival)["state"] == "succeeded"
    assert confirm(client, wh, move)["state"] == "failed"
    with app.state.sessions() as db:
        assert db.get(Booking, winning_booking).slot_id == "slot-0"
        assert db.get(Reservation, "slot-0").booking_id == winning_booking
    good_move = proposal(client, wh, "slot-2", "move-key-2", "reschedule", winning_booking)
    assert confirm(client, wh, good_move)["state"] == "succeeded"
    with app.state.sessions() as db:
        assert db.get(Booking, winning_booking).slot_id == "slot-2"
        assert db.get(Reservation, "slot-0") is None


def test_expired_confirmation_and_stale_booking_version(setup):
    from platform_api.database import Operation

    client, app = setup
    booking_seed(app)
    h = auth(client)
    op = proposal(client, h)
    with app.state.sessions.begin() as db:
        db.get(Operation, op["id"]).expires_at = int(time.time()) - 1
    assert confirm(client, h, op)["state"] == "expired"
    booked = confirm(client, h, proposal(client, h, key="book-again-1"))
    move = proposal(client, h, "slot-1", "move-new-1", "reschedule", booked["booking_id"])
    cancel = proposal(client, h, "", "cancel-new-1", "cancel", booked["booking_id"])
    assert confirm(client, h, cancel)["state"] == "succeeded"
    assert confirm(client, h, move)["state"] == "failed"
