"""Inventory installed dependency metadata; unknown licences still require human review."""

import importlib.metadata
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = []
for line in (root / "requirements.txt").read_text().splitlines():
    if not line or line.startswith("#") or "==" not in line:
        continue
    name, version = line.split("==", 1)
    name = name.split("[", 1)[0]
    try:
        metadata = importlib.metadata.metadata(name)
        licence = metadata.get("License-Expression") or metadata.get("License") or "UNKNOWN"
        classifiers = [
            item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")
        ]
        python.append(
            {
                "name": name,
                "version": version,
                "license_metadata": licence.splitlines()[0][:200],
                "license_classifiers": classifiers,
            }
        )
    except importlib.metadata.PackageNotFoundError:
        python.append({"name": name, "version": version, "license_metadata": "NOT INSTALLED"})
lock = json.loads((root / "apps/admin/package-lock.json").read_text())
javascript = [
    {
        "path": path,
        "version": package.get("version"),
        "license_metadata": package.get("license", "UNKNOWN"),
    }
    for path, package in lock["packages"].items()
    if path
]
report = {
    "date": "2026-10-27",
    "notice": "Metadata inventory, not a legal review. UNKNOWN entries need review. Mobile example dependencies are not installed/locked in this project.",
    "python": python,
    "javascript": javascript,
    "model_weights": [
        {
            "tag": "smollm2:135m",
            "license": "Apache-2.0",
            "source": "https://ollama.com/library/smollm2:135m",
        },
        {
            "tag": "smollm2:360m",
            "license": "Apache-2.0",
            "source": "https://ollama.com/library/smollm2:360m",
        },
        {
            "tag": "all-minilm:latest",
            "license": "Apache-2.0",
            "source": "https://ollama.com/library/all-minilm:latest",
        },
    ],
}
(root / "docs/dependency-inventory.json").write_text(json.dumps(report, indent=2) + "\n")
