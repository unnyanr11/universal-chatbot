import pytest
from fastapi.testclient import TestClient
from platform_api.app import create_app, passwords
from platform_api.database import Assistant, Membership, Organization, Project, User
from platform_api.migrate import migrate


@pytest.fixture
def setup(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    migrate(url)
    migrate(url)  # Migration is safe to rerun.
    app = create_app(url)
    with app.state.sessions.begin() as db:
        for name, role in [("cedar", "owner"), ("harbor", "analyst")]:
            org = Organization(id=name, name=name)
            user = User(
                id=name,
                email=f"{name}@example.test",
                password_hash=passwords.hash("a-long-test-password"),
            )
            db.add_all([org, user])
            db.flush()
            db.add(Membership(user_id=name, organization_id=name, role=role))
            db.add(Project(id=name, name=name, organization_id=name))
            db.flush()
            db.add(Assistant(project_id=name, name=f"{name} assistant", welcome_message="Hi"))
    with TestClient(app) as client:
        yield client, app
    app.state.engine.dispose()
