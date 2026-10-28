"""Vercel FastAPI entrypoint; install the repository package before importing."""

from platform_api.app import create_app

app = create_app()
