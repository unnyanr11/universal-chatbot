"""Run: APP_URL=https://chat.example ASSISTANT_ID=... python examples/api_client.py."""

import os

import httpx


def main():
    origin = os.environ["APP_URL"].rstrip("/")
    assistant = os.environ["ASSISTANT_ID"]
    # Uses the public guest API; no upstream AI key or admin token belongs in this client.
    with httpx.Client(base_url=origin, timeout=75, trust_env=False) as client:
        session = client.post(f"/v1/public/assistants/{assistant}/sessions", json={})
        session.raise_for_status()
        headers = {"Authorization": "Bearer " + session.json()["access_token"]}
        result = client.post(
            f"/v1/assistants/{assistant}/chat",
            headers=headers,
            json={"text": "What services do you offer?", "mode": "extractive"},
        )
        result.raise_for_status()
        print(result.json()["text"])


if __name__ == "__main__":
    main()
