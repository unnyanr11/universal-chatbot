"""Start isolated synthetic API + worker for real browser acceptance tests."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from platform_api.migrate import migrate
from platform_api.seed import seed


def main():
    with tempfile.TemporaryDirectory() as folder:
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(folder) / "browser.db")
        os.environ["APP_ENV"] = "development"
        os.environ["PROVIDER_SECRET_KEY"] = Fernet.generate_key().decode()
        os.environ["AI_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = ""
        os.environ["DEMO_PASSWORD"] = "synthetic-e2e-password"
        migrate(os.environ["DATABASE_URL"])
        seed()
        worker = subprocess.Popen([sys.executable, "-m", "platform_api.worker"])
        try:
            import uvicorn

            uvicorn.run("platform_api.app:create_app", factory=True, host="127.0.0.1", port=8000)
        finally:
            worker.terminate()
            worker.wait(timeout=10)


if __name__ == "__main__":
    main()
