"""First-run acceptance and credential-preserving installer configuration."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from platform_api.app import create_app, passwords
from platform_api.bootstrap import InitialOwner, initialize
from platform_api.database import Assistant, Document, User, connect
from platform_api.migrate import migrate
from sqlalchemy import func, select

spec = importlib.util.spec_from_file_location(
    "installer", Path(__file__).parents[1] / "scripts/setup.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_first_owner_gets_usable_workspace_without_demo_users(tmp_path):
    url = f"sqlite:///{tmp_path / 'setup.db'}"
    migrate(url)
    engine, sessions = connect(url)
    owner = InitialOwner(
        email="OWNER@example.test", name="Actual business", password="a-private-long-password"
    )
    result = initialize(sessions, owner)
    assert result["created"]
    assert initialize(sessions, owner) == {"created": False}
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        user = db.scalar(select(User))
        assert user.email == "owner@example.test"
        assert passwords.verify(owner.password, user.password_hash)
        assert db.scalar(select(Assistant)).name == "My assistant"
        assert db.get(Document, result["document_id"]).status == "queued"
    app = create_app(url)
    with TestClient(app) as client:
        login = client.post("/v1/sessions", json={"email": owner.email, "password": owner.password})
        assert login.status_code == 201
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        project = client.get("/v1/projects", headers=headers).json()["items"][0]
        assistants = client.get(f"/v1/projects/{project['id']}/assistants", headers=headers)
        assert assistants.status_code == 200 and len(assistants.json()["items"]) == 1
    app.state.engine.dispose()
    engine.dispose()


def test_installer_preserves_credentials_and_validates_public_input(tmp_path):
    values = installer.configure({}, domain="chat.example.test", port=8001, source_only=False)
    path = tmp_path / ".env"
    installer.write_config(path, values)
    assert installer.read_config(path) == values
    rerun = installer.configure(
        installer.read_config(path), domain=None, port=None, source_only=False
    )
    assert rerun == values
    assert len(values["POSTGRES_PASSWORD"]) == 64
    assert values["OLLAMA_MODEL"] and values["OLLAMA_EMBED_MODEL"]
    for domain in (
        "https://chat.example.test",
        "127.0.0.1",
        "bad_domain.test",
        "-chat.example.test",
        "example.test/path",
    ):
        with pytest.raises(installer.SetupError):
            installer.configure(values, domain=domain, port=None, source_only=False)
    with pytest.raises(installer.SetupError):
        installer.configure(values, domain=None, port=-1, source_only=False)
    baseline = installer.configure(values, domain=None, port=None, source_only=True)
    assert baseline["OLLAMA_MODEL"] == baseline["OLLAMA_EMBED_MODEL"] == ""


def test_installer_child_processes_receive_only_explicit_input():
    import sys

    command = [sys.executable, "-c", "import sys; print(sys.stdin.read(), end='')"]
    assert installer.run(command, capture=True) == ""
    assert installer.run(command, capture=True, data="synthetic-input") == "synthetic-input"


def test_cloud_setup_preserves_master_key_and_never_reuses_another_provider_key():
    base = installer.configure({}, domain="", port=None, source_only=False)
    cloud = installer.configure_ai(
        base, provider="kimi", model="account-model", api_key="synthetic-kimi-key"
    )
    assert cloud["OLLAMA_MODEL"] == "" and cloud["OLLAMA_EMBED_MODEL"]
    assert cloud["AI_PROVIDER"] == "kimi"
    assert installer.configure_ai(cloud) == cloud
    with pytest.raises(installer.SetupError):
        installer.configure_ai(cloud, provider="deepseek", model="another-model")
    changed = installer.configure_ai(
        cloud, provider="deepseek", model="another-model", api_key="synthetic-deepseek-key"
    )
    assert changed["PROVIDER_SECRET_KEY"] == cloud["PROVIDER_SECRET_KEY"]
    assert changed["POSTGRES_PASSWORD"] == cloud["POSTGRES_PASSWORD"]
    assert changed["AI_API_KEY"] == "synthetic-deepseek-key"
    custom = installer.configure_ai(
        changed,
        provider="custom",
        model="private-model",
        api_key="synthetic-custom-key",
        base_url="https://approved.example.test/v1",
    )
    assert custom["AI_CUSTOM_BASE_URLS"] == "https://approved.example.test/v1"
