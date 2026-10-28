"""Fetch HTML over the frontend binding while retaining API embedding policy."""

import logging

import httpx
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


def mount_frontend(app, base_url):
    # Only fixed HTML paths are proxied. Never forward cookies, tokens or queries.
    async def page(filename):
        try:
            # Binding traffic uses the deployment's proxy and certificate settings.
            async with httpx.AsyncClient(timeout=10, trust_env=True) as client:
                response = await client.get(base_url.rstrip("/") + "/admin/" + filename)
            if response.status_code != 200:
                logger.warning(
                    "Frontend binding failed: page=%s status=%s", filename, response.status_code
                )
                raise HTTPException(503, "FRONTEND_UNAVAILABLE")
        except httpx.HTTPError as exc:
            logger.warning(
                "Frontend binding failed: page=%s error=%s", filename, type(exc).__name__
            )
            raise HTTPException(503, "FRONTEND_UNAVAILABLE") from None
        return HTMLResponse(response.content)

    @app.get("/", include_in_schema=False)
    async def studio():
        return await page("index.html")

    @app.get("/chat.html", include_in_schema=False)
    async def chat():
        return await page("chat.html")

    @app.get("/demo-embed.html", include_in_schema=False)
    async def demo():
        return await page("demo-embed.html")
