from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from platform_api.calendars import local_timestamp
from platform_api.database import ResourceReservation
from sqlalchemy import select
from test_booking import booking_seed, confirm, proposal
from test_foundation import auth


def test_staff_calendar_capacity_across_services_and_policy_invalidation(setup):
    client, app = setup
    booking_seed(app)
    h, other = auth(client), auth(client, "second")
    root = "/v1/projects/cedar"
    staff = client.post(root + "/staff", headers=h, json={"name": "Alex technician"}).json()["id"]
    day = datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    services = []
    for name in ["Repair", "Inspection"]:
        service = client.post(root + "/services", headers=h, json={"name": name, "staff_id": staff})
        assert service.status_code == 201, service.text
        service = service.json()["id"]
        assert (
            client.post(
                root + f"/services/{service}/generate-slots",
                headers=h,
                json={"start_date": day.isoformat(), "days": 1},
            ).status_code
            == 200
        )
        slots = client.get(root + f"/services/{service}/slots", headers=h).json()["items"]
        assert slots
        services.append((service, slots))
    assert services[0][1][0]["start_at"] == services[1][1][0]["start_at"]
    first = proposal(client, h, services[0][1][0]["slot_id"], "resource-1")
    second = proposal(client, other, services[1][1][0]["slot_id"], "resource-2")

    def commit(pair):
        with TestClient(app) as parallel:
            return confirm(parallel, *pair)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(commit, [(h, first), (other, second)]))
    assert sorted(r["state"] for r in results) == ["failed", "succeeded"]
    with app.state.sessions() as db:
        assert len(db.scalars(select(ResourceReservation)).all()) == 1
    service, slots = services[0]
    pending = proposal(client, h, slots[-1]["slot_id"], "new-policy-1")
    policy = client.get(root + f"/services/{service}/policy", headers=h).json()
    policy["policy"]["lead_time_minutes"] = 120
    assert (
        client.put(
            root + f"/services/{service}/policy",
            headers=h,
            json={"revision": policy["revision"], "policy": policy["policy"]},
        ).status_code
        == 200
    )
    failed = confirm(client, h, pending)
    assert failed["state"] == "failed" and failed["error"] == "CALENDAR_POLICY_CHANGED_REVIEW_AGAIN"


def test_dst_ambiguous_and_nonexistent_local_times_are_not_guessed():
    from datetime import date

    zone = ZoneInfo("America/New_York")
    assert local_timestamp(date(2026, 3, 8), "02:30", zone) is None
    assert local_timestamp(date(2026, 11, 1), "01:30", zone) is None
    assert local_timestamp(date(2026, 11, 1), "09:00", zone) is not None


def test_generated_slots_skip_ambiguous_times_inside_opening_period(setup, monkeypatch):
    from types import SimpleNamespace

    import platform_api.calendars as calendars

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 27, 12, tzinfo=tz)

    monkeypatch.setattr(calendars, "datetime", FixedDateTime)
    monkeypatch.setattr(
        calendars,
        "time",
        SimpleNamespace(
            time=lambda: datetime(2026, 10, 27, 12, tzinfo=ZoneInfo("UTC")).timestamp()
        ),
    )
    client, app = setup
    h = auth(client)
    root = "/v1/projects/cedar"
    staff = client.post(root + "/staff", headers=h, json={"name": "DST technician"}).json()["id"]
    service = client.post(
        root + "/services",
        headers=h,
        json={
            "name": "DST service",
            "staff_id": staff,
            "timezone": "America/New_York",
            "policy": {"opening_hours": {"6": [["00:00", "04:00"]]}},
        },
    ).json()["id"]
    generated = client.post(
        root + f"/services/{service}/generate-slots",
        headers=h,
        json={"start_date": "2026-11-01", "days": 1},
    )
    assert generated.status_code == 200 and generated.json()["skipped_dst_slots"] >= 4
    from platform_api.database import Slot

    with app.state.sessions() as db:
        for slot in db.scalars(select(Slot).where(Slot.service_id == service)):
            local = datetime.fromtimestamp(slot.start_at, ZoneInfo("America/New_York"))
            assert local.hour != 1
