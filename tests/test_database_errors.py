import logging

from fastapi.testclient import TestClient
from platform_api.app import create_app
from platform_api.migrate import migrate
from sqlalchemy import event
from sqlalchemy.exc import OperationalError


def test_login_database_failure_is_safe_and_recovery_does_not_require_restart(tmp_path, caplog):
    url = f"sqlite:///{tmp_path / 'database.db'}"
    migrate(url)
    app = create_app(url)
    private_detail = "postgresql://private-user:private-password@private-host/database"

    def unavailable(*args):
        raise OperationalError("private query", {}, Exception(private_detail))

    event.listen(app.state.engine, "before_cursor_execute", unavailable)
    try:
        with TestClient(app) as client, caplog.at_level(logging.ERROR):
            credentials = {"email": "owner@example.test", "password": "private-login-password"}
            response = client.post("/v1/sessions", json=credentials)
            assert response.status_code == 503
            error = response.json()["error"]
            assert error["code"] == "DATABASE_UNAVAILABLE"
            assert error["request_id"] == response.headers["X-Request-ID"]
            assert response.headers["Cache-Control"] == "no-store"
            assert private_detail not in response.text + caplog.text
            assert credentials["password"] not in response.text + caplog.text
            assert "private query" not in response.text + caplog.text
            assert error["request_id"] in caplog.text
            assert client.get("/health").status_code == 200

            event.remove(app.state.engine, "before_cursor_execute", unavailable)
            response = client.post("/v1/sessions", json=credentials)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    finally:
        app.state.engine.dispose()
