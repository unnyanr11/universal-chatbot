"""Small DNS-pinned public HTTPS client for reviewed pages and approved webhooks."""

import http.client
import ipaddress
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


class RemoteError(ValueError):
    pass


def public_address(host):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(
            (
                not ipaddress.ip_address(address).is_global
                or ipaddress.ip_address(address).is_multicast
                or ipaddress.ip_address(address).is_reserved
            )
            for address in addresses
        ):
            raise RemoteError("URL must resolve only to public addresses")
        return sorted(addresses)[0]
    except (OSError, ValueError):
        raise RemoteError("Website address is unavailable or not public") from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=5, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        connection = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
        except BaseException:
            connection.close()
            raise


def fetch(url, *, method="GET", body=None, headers=None):
    """No cookies, proxies or credential redirects. Resolve/validate/pin each target."""
    deadline = time.monotonic() + 15
    original_host = urlsplit(url).hostname
    for _ in range(4):
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.port not in {None, 443}
            or parts.fragment
        ):
            raise RemoteError("Use a public HTTPS URL without credentials, fragment or custom port")
        connection = PinnedHTTPS(parts.hostname, public_address(parts.hostname))
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request(
                method,
                path,
                body=body,
                headers={
                    "User-Agent": "AssistantStudio/1.0 (+reviewed-import)",
                    "Accept": "text/html,application/json",
                    "Accept-Encoding": "identity",
                    **(headers or {}),
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                if method != "GET":
                    raise RemoteError("Webhook redirects are not followed")
                url = urljoin(url, response.getheader("Location", ""))
                if urlsplit(url).hostname != original_host:
                    raise RemoteError("Cross-host redirects need a separately selected URL")
                continue
            data = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise RemoteError("Remote request exceeded time budget")
                block = response.read1(16384)
                if not block:
                    break
                data.extend(block)
                if len(data) > 2_000_000:
                    raise RemoteError("Remote response exceeds 2 MB")
            return response.status, response.getheader("Content-Type", ""), bytes(data), url
        except (OSError, http.client.HTTPException):
            raise RemoteError("Remote request failed; check URL, TLS and availability") from None
        finally:
            connection.close()
    raise RemoteError("Too many redirects")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.scripts = [], []
        self.hidden = 0
        self.title_depth = 0
        self.title = ""
        self.color, self.font = "#1e5548", "system-ui"
        self.nodes = 0

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > 20000:
            raise RemoteError("Page structure exceeds import budget")
        values = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        if tag == "script":
            self.scripts.append(values)
        if tag == "title":
            self.title_depth += 1
        if tag == "meta" and values.get("name", "").lower() == "theme-color":
            import re

            color = values.get("content", "")
            if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                self.color = color
        style = values.get("style", "").lower()
        for font in ("georgia", "verdana", "arial"):
            if "font-family" in style and font in style:
                self.font = font
        if tag in {"p", "br", "h1", "h2", "h3", "li", "section", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, value):
        if self.title_depth:
            self.title += value[:200]
        if not self.hidden:
            self.parts.append(value)


def read_page(url):
    status, kind, data, final_url = fetch(url)
    if status != 200 or "text/html" not in kind:
        raise RemoteError("URL must return an accessible HTML page")
    page = Page()
    page.feed(data.decode("utf-8", errors="replace"))
    text = "\n".join(line.strip() for line in "".join(page.parts).splitlines() if line.strip())[
        :40000
    ]
    if not text:
        raise RemoteError("No readable HTML text found; upload an approved document instead")
    return {
        "url": final_url,
        "title": page.title.strip()[:150] or urlsplit(url).hostname,
        "text": text,
        "color": page.color,
        "font_family": page.font,
        "scripts": page.scripts,
    }
