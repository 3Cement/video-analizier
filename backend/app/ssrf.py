from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.aws.internal"}


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) URLs are allowed")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in _BLOCKED_HOSTS or hostname.endswith(".localhost"):
        raise ValueError("Private network URLs are not allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))}
    except socket.gaierror as exc:
        raise ValueError("URL hostname could not be resolved") from exc
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if not ip.is_global:
            raise ValueError("Private network URLs are not allowed")
    return url


def safe_get(client: httpx.Client, url: str, *, max_redirects: int = 5) -> httpx.Response:
    current = url
    for _ in range(max_redirects + 1):
        validate_public_url(current)
        response = client.get(current, follow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                return response
            current = urljoin(current, location)
            continue
        return response
    raise ValueError("Too many redirects")
