import asyncio
import json
import os
import platform
import shutil

from .inference import OllamaProvider


async def main():
    memory = None
    if hasattr(os, "sysconf"):
        memory = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1)
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "ram_gib": memory,
                "free_disk_gib": round(shutil.disk_usage(".").free / 1024**3, 1),
                "docker_installed": bool(shutil.which("docker")),
                "ollama_installed": bool(shutil.which("ollama")),
                "gpu": "not measured; inspect VRAM before choosing a model",
                "provider": await OllamaProvider(
                    os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                    os.getenv("OLLAMA_MODEL", ""),
                ).check(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
