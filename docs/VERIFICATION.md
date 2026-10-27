# Verification — 27 October 2026

Executed in this environment:

- Dependency installation succeeded in a fresh Python 3.12 virtual environment.
- `ruff check .` passed; `ruff format --check .` passed.
- `pytest -q`: 6 passed in approximately 3 seconds.
- `pip check`: no broken requirements.
- Explicit migration and synthetic seed succeeded against a separate native SQLite database.
- Live Uvicorn HTTP smoke: health, seeded login, scoped project list, draft creation, logout and revoked-token rejection passed.
- Doctor: approximately 9.7 GiB visible RAM, 29.7 GiB free disk; Docker/Ollama absent, GPU not measured, provider unconfigured.

A Starlette warning reports that its httpx TestClient integration is deprecated in favour of httpx2. The installed, pinned combination still passes tests; migrate the test transport before a future dependency upgrade removes compatibility.

The first live smoke attempt inherited the host's SOCKS proxy setting and failed before making requests. A second attempt could not reach a server started in a separate execution session. Running server and client together with environment proxy discovery disabled passed. The application Ollama adapter already disables environment proxy discovery for local inference.

Not executed: Docker build/Compose, PostgreSQL migration/concurrency, actual model download/inference, React/browser/mobile checks, vulnerability/complete licence scans. Adapter tests use an explicitly labelled HTTP transport double and do not count as real AI inference. No knowledge, booking, external side-effect or production-security acceptance is claimed.
