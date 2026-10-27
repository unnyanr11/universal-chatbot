"""Bounded extraction subprocess: no OCR, no network, no execution of document code."""

import io
import json
import sys
import zipfile
from xml.etree import ElementTree


def extract(data: bytes, kind: str):
    if kind == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("Encrypted or oversized PDF")
        pages = []
        for number, page in enumerate(reader.pages, 1):
            stream = page.get_contents()
            if stream and len(stream.get_data()) > 8_000_000:
                raise ValueError("PDF page exceeds extraction budget")
            pages.append((number, page.extract_text() or ""))
    elif kind == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(e.file_size for e in entries) > 32_000_000:
                raise ValueError("Archive exceeds extraction budget")
            info = archive.getinfo("word/document.xml")
            if info.file_size > 8_000_000:
                raise ValueError("Document XML exceeds extraction budget")
            document = ElementTree.fromstring(archive.read(info))
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            text = "\n\n".join(
                "".join(t.text or "" for t in paragraph.iter(namespace + "t"))
                for paragraph in document.iter(namespace + "p")
            )
            pages = [(1, text)]  # DOCX has no stable page numbers without layout rendering.
    else:
        text = data.decode("utf-8")
        if "\x00" in text:
            raise ValueError("Binary content is not text")
        pages = [(1, text)]
    result = []
    total = 0
    for page, text in pages:
        text = text.strip()
        total += len(text)
        if total > 500_000:
            raise ValueError("Extracted text exceeds budget")
        # Bounded paragraph-aware chunks, preserving page metadata.
        for paragraph in text.split("\n\n"):
            for start in range(0, len(paragraph), 900):
                chunk = paragraph[start : start + 1000].strip()
                if chunk:
                    result.append({"page": page, "text": chunk})
    if not result:
        raise ValueError("No extractable text; scanned PDFs need OCR (unsupported)")
    return result


if __name__ == "__main__":
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    except ImportError:
        pass  # Windows still enforces the parent's wall-clock timeout.
    try:
        print(json.dumps(extract(sys.stdin.buffer.read(2_000_001), sys.argv[1])))
    except Exception:
        sys.exit(2)
