import time

from platform_api.database import Booking, WorkflowRun
from sqlalchemy import select
from test_booking import booking_seed
from test_foundation import auth
from test_knowledge import bot_id, upload_ready


def test_configuration_publish_pins_sources_and_restores_versions(setup):
    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    root = f"/v1/assistants/{assistant}"
    upload_ready(client, app, h, assistant, "Warranty lasts twelve months.")
    config = client.get(root + "/configuration", headers=h).json()
    config["configuration"]["name"] = "Published helper"
    saved = client.put(
        root + "/configuration",
        headers=h,
        json={"revision": config["revision"], "configuration": config["configuration"]},
    )
    assert saved.status_code == 200
    assert (
        client.put(
            root + "/configuration",
            headers=h,
            json={"revision": 0, "configuration": config["configuration"]},
        ).status_code
        == 409
    )
    published = client.post(
        root + "/publish", headers=h, json={"revision": saved.json()["revision"]}
    )
    assert published.status_code == 200 and published.json()["published_version"] == 1
    upload_ready(client, app, h, assistant, "Returns accepted within fourteen days.", "returns.txt")
    assert client.get(root + "/search?q=Returns", headers=h).json()["items"] == []
    second = client.post(
        root + "/publish", headers=h, json={"revision": published.json()["revision"]}
    )
    assert second.status_code == 200 and second.json()["published_version"] == 2
    assert client.get(root + "/search?q=Returns", headers=h).json()["items"]
    restored = client.post(
        root + "/versions/1/restore", headers=h, json={"revision": second.json()["revision"]}
    )
    assert restored.status_code == 200
    assert client.get(root + "/search?q=Returns", headers=h).json()["items"] == []
    assert client.get(root + "/configuration", headers=auth(client, "harbor")).status_code == 404


def test_handoff_pauses_automation_and_notes_stay_private(setup):
    client, app = setup
    booking_seed(app)
    customer, agent = auth(client, "second"), auth(client)
    assistant = bot_id(client, agent)
    bot = f"/v1/assistants/{assistant}"
    conv = client.post(bot + "/chat", headers=customer, json={"text": "I need help"}).json()[
        "conversation_id"
    ]
    ticket = client.post(
        "/v1/projects/cedar/tickets",
        headers=customer,
        json={"conversation_id": conv, "subject": "Repair question"},
    )
    assert ticket.status_code == 201
    root = "/v1/projects/cedar/tickets/" + ticket.json()["id"]
    paused = client.post(
        bot + "/chat", headers=customer, json={"text": "Please assist", "conversation_id": conv}
    )
    assert paused.json()["mode"] == "handoff"
    assert (
        client.post(
            root + "/state", headers=customer, json={"action": "claim", "version": 1}
        ).status_code
        == 403
    )
    claimed = client.post(root + "/state", headers=agent, json={"action": "claim", "version": 1})
    assert claimed.status_code == 200
    assert (
        client.post(
            root + "/messages", headers=agent, json={"text": "PRIVATE AGENT NOTE", "internal": True}
        ).status_code
        == 201
    )
    assert (
        client.post(
            root + "/messages", headers=agent, json={"text": "A human can help you."}
        ).status_code
        == 201
    )
    transcript = client.get(bot + "/conversations/" + conv, headers=customer)
    assert "A human can help" in transcript.text and "PRIVATE AGENT NOTE" not in transcript.text
    assert "notes" not in client.get(root, headers=customer).json()
    assert "PRIVATE AGENT NOTE" in client.get(root, headers=agent).text
    assert (
        "PRIVATE AGENT NOTE" not in client.get("/v1/projects/cedar/my-data", headers=customer).text
    )
    assert (
        client.post(
            root + "/state",
            headers=agent,
            json={"action": "resume", "version": claimed.json()["version"]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            bot + "/chat", headers=customer, json={"text": "hello", "conversation_id": conv}
        ).json()["mode"]
        == "extractive"
    )
    assert client.get(root, headers=auth(client, "harbor")).status_code == 404


def test_workflow_version_dry_run_live_confirmation_and_recovery(setup):
    client, app = setup
    booking_seed(app)
    h = auth(client)
    root = "/v1/projects/cedar"
    definition = {
        "name": "Book consultation",
        "nodes": [
            {"type": "collect", "key": "slot", "label": "Choose a slot ID"},
            {"type": "propose_booking", "key": "proposal", "arguments": {"slot_id": "$slot"}},
            {"type": "confirmation", "key": "result", "label": "Confirm appointment"},
            {"type": "end"},
        ],
    }
    workflow = client.post(root + "/workflows", headers=h, json=definition)
    assert workflow.status_code == 201
    url = root + "/workflows/" + workflow.json()["id"]
    dry = client.post(
        url + "/runs", headers=h, json={"version": 1, "idempotency_key": "dry-workflow-1"}
    ).json()
    assert dry["state"] == "waiting" and dry["dry_run"]
    dry = client.post(
        root + "/workflow-runs/" + dry["id"] + "/resume",
        headers=h,
        json={"revision": dry["revision"], "value": "slot-0"},
    ).json()
    assert dry["state"] == "awaiting_confirmation" and "approval" not in dry
    with app.state.sessions() as db:
        assert not db.scalars(select(Booking)).all()
    run = client.post(
        url + "/runs",
        headers=h,
        json={"version": 1, "idempotency_key": "live-workflow-1", "dry_run": False},
    ).json()
    run = client.post(
        root + "/workflow-runs/" + run["id"] + "/resume",
        headers=h,
        json={"revision": run["revision"], "value": "slot-0"},
    ).json()
    assert (
        run["state"] == "awaiting_confirmation"
        and run["approval"]["state"] == "awaiting_confirmation"
    )
    assert (
        client.post(
            url + "/versions",
            headers=h,
            json={"name": "New definition", "nodes": [{"type": "end"}]},
        ).status_code
        == 201
    )
    # Stored run stays pinned to v1 after v2 is saved and after a simulated process crash.
    with app.state.sessions.begin() as db:
        record = db.get(WorkflowRun, run["id"])
        record.state, record.lease_until = "running", int(time.time()) - 1
    finished = client.post(
        root + "/workflow-runs/" + run["id"] + "/resume",
        headers=h,
        json={"revision": run["revision"], "approve": True},
    ).json()
    assert finished["state"] == "succeeded", finished
    repeated = client.post(
        url + "/runs",
        headers=h,
        json={"version": 1, "idempotency_key": "live-workflow-1", "dry_run": False},
    ).json()
    assert repeated["id"] == finished["id"] and repeated["state"] == "succeeded"
    with app.state.sessions() as db:
        assert len(db.scalars(select(Booking)).all()) == 1


def test_workspace_privacy_memory_and_session_controls(setup):
    client, app = setup
    booking_seed(app)
    h = auth(client)
    root = "/v1/projects/cedar"
    assert (
        client.post(
            root + "/memories", headers=h, json={"text": "Prefer concise replies", "consent": False}
        ).status_code
        == 422
    )
    memory = client.post(
        root + "/memories", headers=h, json={"text": "Prefer concise replies", "consent": True}
    )
    assert memory.status_code == 201
    assert client.get(root + "/memories", headers=auth(client, "second")).json()["items"] == []
    assert (
        client.get(root + "/my-data", headers=h).json()["memories"][0]["text"]
        == "Prefer concise replies"
    )
    assert (
        client.request(
            "DELETE", root + "/my-data", headers=h, json={"confirmation": "wrong"}
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE",
            root + "/my-data",
            headers=h,
            json={"confirmation": "DELETE MY WORKSPACE DATA"},
        ).status_code
        == 204
    )
    assert client.get(root + "/memories", headers=h).json()["items"] == []
    assert client.delete("/v1/me/sessions", headers=h).status_code == 204
    assert client.get("/v1/me", headers=h).status_code == 401


def test_workflow_rejects_code_nodes_cycles_and_cross_tenant_runs(setup):
    client, _ = setup
    h = auth(client)
    root = "/v1/projects/cedar"
    assert (
        client.post(
            root + "/workflows",
            headers=h,
            json={
                "name": "Unsafe",
                "nodes": [{"type": "shell", "arguments": {"command": "ls"}}, {"type": "end"}],
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            root + "/workflows",
            headers=h,
            json={
                "name": "Loop",
                "nodes": [{"type": "branch", "key": "x", "target": 0}, {"type": "end"}],
            },
        ).status_code
        == 422
    )
    assert client.get(root + "/workflow-runs", headers=auth(client, "harbor")).status_code == 404


def test_widget_frame_allowlist_is_enforced_as_defence_in_depth(setup):
    client, _ = setup
    h = auth(client)
    assistant = bot_id(client, h)
    root = f"/v1/assistants/{assistant}"
    cfg = client.get(root + "/configuration", headers=h).json()
    cfg["configuration"]["allowed_domains"] = ["example.com", "localhost:3000"]
    assert (
        client.put(
            root + "/configuration",
            headers=h,
            json={"revision": 0, "configuration": cfg["configuration"]},
        ).status_code
        == 200
    )
    response = client.get(f"/?widget=1&assistant={assistant}")
    policy = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'self' https://example.com http://localhost:3000" in policy
    assert client.get("/").headers["Content-Security-Policy"].endswith("frame-ancestors 'self'")


def test_invitation_one_time_membership_removal_and_credential_rotation(setup):
    client, app = setup
    h = auth(client)
    root = "/v1/projects/cedar"
    invite = client.post(
        root + "/invitations", headers=h, json={"email": "invited@example.test", "role": "end_user"}
    )
    assert invite.status_code == 201 and "No email" in invite.json()["delivery"]
    body = {
        "token": invite.json()["token"],
        "email": "invited@example.test",
        "password": "new-account-test-password",
    }
    assert client.post("/v1/invitations/register", json=body).status_code == 201
    assert client.post("/v1/invitations/register", json=body).status_code == 409
    login = client.post(
        "/v1/sessions", json={"email": body["email"], "password": body["password"]}
    ).json()
    user = {"Authorization": "Bearer " + login["access_token"]}
    me = client.get("/v1/me", headers=user).json()
    assert client.get(root + "/services", headers=user).status_code == 200
    assert (
        client.post(
            root + "/invitations", headers=user, json={"email": "other@example.test"}
        ).status_code
        == 403
    )
    assert client.delete(root + "/members/cedar", headers=h).status_code == 409
    assert client.delete(root + "/members/" + me["id"], headers=h).status_code == 204
    assert client.get("/v1/me", headers=user).status_code == 401
    assert (
        client.post(
            "/v1/me/password",
            headers=h,
            json={"current_password": "wrong", "new_password": "another-test-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/me/password",
            headers=h,
            json={
                "current_password": "a-long-test-password",
                "new_password": "another-test-password",
            },
        ).status_code
        == 204
    )
    assert client.get("/v1/me", headers=h).status_code == 401
