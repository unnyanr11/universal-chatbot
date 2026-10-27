import io
import time

from platform_api.database import Job
from platform_api.worker import run_once
from sqlalchemy import select
from test_foundation import auth


def bot_id(client, headers, project="cedar"):
    return client.get(f"/v1/projects/{project}/assistants", headers=headers).json()["items"][0][
        "id"
    ]


def upload_ready(client, app, headers, assistant, text, filename="faq.txt"):
    r = client.post(
        f"/v1/assistants/{assistant}/documents",
        headers=headers,
        files={"file": (filename, text.encode(), "text/plain")},
    )
    assert r.status_code == 202, r.text
    run_once(app.state.sessions)
    docs = client.get(f"/v1/assistants/{assistant}/documents", headers=headers).json()["items"]
    assert next(d for d in docs if d["id"] == r.json()["id"])["status"] == "ready"
    return r.json()["id"]


def test_ingestion_retrieval_chat_and_source_removal(setup):
    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    doc = upload_ready(
        client,
        app,
        h,
        assistant,
        "Cedar repairs bicycles. Business hours are 09:00 to 17:00 weekdays.",
    )
    root = f"/v1/assistants/{assistant}"
    answer = client.post(
        root + "/chat", headers=h, json={"text": "What are business hours?"}
    ).json()
    assert "09:00" in answer["text"]
    assert answer["citations"][0]["document_id"] == doc
    chunk_id = answer["citations"][0]["chunk_id"]
    assert client.get(root + "/sources/" + chunk_id, headers=h).status_code == 200
    missing = client.post(
        root + "/chat", headers=h, json={"text": "Explain interstellar photosynthesis"}
    ).json()
    assert "enough information" in missing["text"]
    assert not missing["citations"]
    assert client.delete(root + "/documents/" + doc, headers=h).status_code == 204
    assert client.get(root + "/sources/" + chunk_id, headers=h).status_code == 404
    transcript = client.get(root + "/conversations/" + answer["conversation_id"], headers=h)
    assert "09:00" not in transcript.text
    assert client.get(root + "/search?q=hours", headers=h).json()["items"] == []


def test_knowledge_isolation_upload_validation_and_duplicate(setup):
    client, app = setup
    owner, other = auth(client), auth(client, "harbor")
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    doc = upload_ready(client, app, owner, assistant, "Private bicycle warranty policy.")
    assert client.get(root + "/documents", headers=other).status_code == 404
    assert client.post(root + "/chat", headers=other, json={"text": "warranty"}).status_code == 404
    duplicate = client.post(
        root + "/documents",
        headers=owner,
        files={"file": ("same.txt", b"Private bicycle warranty policy.")},
    )
    assert duplicate.json()["id"] == doc
    assert duplicate.json()["duplicate"]
    assert (
        client.post(
            root + "/documents", headers=owner, files={"file": ("fake.pdf", b"not a PDF")}
        ).status_code
        == 415
    )
    assert (
        client.post(
            root + "/documents", headers=owner, files={"file": ("binary.txt", b"a\x00b")}
        ).status_code
        == 415
    )
    assert (
        client.post(
            root + "/documents", headers=owner, files={"file": ("huge.txt", b"a" * 2_000_001)}
        ).status_code
        == 413
    )


def test_job_lease_recovers_and_failed_extraction_is_visible(setup):
    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    root = f"/v1/assistants/{assistant}"
    r = client.post(
        root + "/documents", headers=h, files={"file": ("recover.txt", b"Recoverable text")}
    )
    with app.state.sessions.begin() as db:
        job = db.scalar(select(Job).where(Job.document_id == r.json()["id"]))
        job.state, job.lease_until, job.attempts = "running", int(time.time()) - 1, 1
    assert run_once(app.state.sessions)
    assert not run_once(app.state.sessions)
    docs = client.get(root + "/documents", headers=h).json()["items"]
    assert docs[0]["status"] == "ready"
    client.post(root + "/documents", headers=h, files={"file": ("empty.txt", b"  ")})
    run_once(app.state.sessions)
    docs = client.get(root + "/documents", headers=h).json()["items"]
    assert any(d["status"] == "failed" and d["error"] for d in docs)


def test_real_pdf_extraction_and_sse_contract(setup):
    from reportlab.pdfgen import canvas

    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(40, 750, "Cedar bicycle maintenance costs thirty demo credits.")
    page.save()
    root = f"/v1/assistants/{assistant}"
    r = client.post(
        root + "/documents", headers=h, files={"file": ("price.pdf", buffer.getvalue())}
    )
    assert r.status_code == 202
    run_once(app.state.sessions)
    r = client.post(
        root + "/chat",
        headers={**h, "Accept": "text/event-stream"},
        json={"text": "bicycle maintenance"},
    )
    assert r.status_code == 200
    assert "event: result" in r.text and "thirty" in r.text and "event: done" in r.text


def test_docx_csv_and_exhausted_job_budget(setup):
    import zipfile

    client, app = setup
    headers = auth(client)
    assistant = bot_id(client, headers)
    root = f"/v1/assistants/{assistant}"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as docx:
        docx.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>DOCX warranty lasts twelve months.</w:t></w:r></w:p></w:body></w:document>',
        )
    response = client.post(
        root + "/documents", headers=headers, files={"file": ("warranty.docx", archive.getvalue())}
    )
    assert response.status_code == 202
    run_once(app.state.sessions)
    assert client.get(root + "/search?q=warranty", headers=headers).json()["items"]
    upload_ready(client, app, headers, assistant, "question,answer\nDelivery,Five days", "faq.csv")
    assert client.get(root + "/search?q=Delivery", headers=headers).json()["items"]
    response = client.post(
        root + "/documents",
        headers=headers,
        files={"file": ("exhausted.txt", b"No worker finished this document.")},
    )
    with app.state.sessions.begin() as db:
        job = db.scalar(select(Job).where(Job.document_id == response.json()["id"]))
        job.state, job.attempts, job.lease_until = "running", 3, 0
    run_once(app.state.sessions)
    document = next(
        d
        for d in client.get(root + "/documents", headers=headers).json()["items"]
        if d["id"] == response.json()["id"]
    )
    assert document["status"] == "failed" and "retry budget" in document["error"]


def test_citation_numbering_preserves_retrieval_order(setup):
    client, app = setup
    headers = auth(client)
    assistant = bot_id(client, headers)
    upload_ready(
        client, app, headers, assistant, "Bicycle warranty lasts twelve months.", "terms.txt"
    )
    upload_ready(
        client,
        app,
        headers,
        assistant,
        "Warranty warranty warranty warranty details.",
        "warranty.txt",
    )
    root = f"/v1/assistants/{assistant}"
    expected = client.get(root + "/search?q=warranty", headers=headers).json()["items"]
    assert len(expected) == 2
    result = client.post(root + "/chat", headers=headers, json={"text": "warranty"}).json()
    assert [c["chunk_id"] for c in result["citations"]] == [c["chunk_id"] for c in expected]
    for index, chunk in enumerate(result["citations"], 1):
        assert f"[{index}] {chunk['text']}" in result["text"]


def test_short_follow_up_uses_owned_conversation_context(setup):
    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    upload_ready(client, app, h, assistant, "Bicycle service costs thirty credits.")
    root = f"/v1/assistants/{assistant}"
    first = client.post(root + "/chat", headers=h, json={"text": "Bicycle service"}).json()
    follow_up = client.post(
        root + "/chat",
        headers=h,
        json={"text": "How much is it?", "conversation_id": first["conversation_id"]},
    ).json()
    assert "thirty credits" in follow_up["text"] and follow_up["citations"]
    assert follow_up["conversation_id"] == first["conversation_id"]
