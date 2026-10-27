"""Small reproducible lexical baseline. No model-accuracy or security guarantee."""

import json
import tempfile
from pathlib import Path

from platform_api.database import Assistant, Chunk, Document, Organization, Project, connect
from platform_api.knowledge import retrieve
from platform_api.migrate import migrate


def main():
    cases = json.loads(Path(__file__).with_name("faq_cases.json").read_text())
    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{folder}/evaluation.db"
        migrate(url)
        engine, sessions = connect(url)
        with sessions.begin() as db:
            db.add(Organization(id="demo", name="Cedar"))
            db.flush()
            db.add(Project(id="demo", name="Demo", organization_id="demo"))
            db.flush()
            db.add(Assistant(id="demo", project_id="demo", name="Demo", welcome_message="Hello"))
            db.flush()
            for key, text in {
                "hours": "Cedar opening hours are 09:00 to 17:00 weekdays.",
                "services": "Cedar offers bicycle repairs and maintenance.",
            }.items():
                db.add(
                    Document(
                        id=key,
                        assistant_id="demo",
                        title=key,
                        content_hash=key,
                        content=text.encode(),
                        kind="txt",
                        status="ready",
                    )
                )
                db.flush()
                db.add(Chunk(document_id=key, ordinal=0, page=1, text=text))
        results = []
        with sessions() as db:
            for case in cases:
                passages = retrieve(db, "demo", case["question"])
                ids = [p["document_id"] for p in passages]
                results.append(
                    {
                        "question": case["question"],
                        "retrieved": ids,
                        "passed": case["source"] in ids if case["source"] else not ids,
                    }
                )
        engine.dispose()
    print(
        json.dumps(
            {
                "dataset": "3 synthetic FAQ smoke cases; not a general benchmark",
                "results": results,
                "passed": sum(r["passed"] for r in results),
                "total": len(results),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
