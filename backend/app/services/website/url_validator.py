from __future__ import annotations

import ipaddress
import posixpath
import socket
import urllib.parse

from fastapi import HTTPException, status

SAFE_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


class UrlValidationService:
    def validate_and_normalize(self, raw_url: str, *, allow_path: bool = True) -> str:
        candidate = raw_url.strip()
        if not candidate or len(candidate) > 2048:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL is missing or too long.")
        if any(ord(char) < 32 for char in candidate):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL contains invalid characters.")

        parsed = urllib.parse.urlsplit(candidate)
        if parsed.scheme.lower() not in SAFE_SCHEMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only HTTP and HTTPS URLs are allowed.")
        if not parsed.netloc or not parsed.hostname:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL must include a valid hostname.")
        if parsed.username or parsed.password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credentials in URLs are not allowed.")
        self._validate_host(parsed.hostname)

        normalized_path = posixpath.normpath(parsed.path or "/")
        if parsed.path.endswith("/") and normalized_path != "/":
            normalized_path = normalized_path.rstrip("/")
        if not allow_path:
            normalized_path = "/"
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        path_part = "" if normalized_path == "/" else normalized_path

        normalized_query = urllib.parse.urlencode(
            sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)),
            doseq=True,
        )
        port = parsed.port
        default_port = (parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)
        netloc = parsed.hostname.lower() if default_port or port is None else f"{parsed.hostname.lower()}:{port}"
        return urllib.parse.urlunsplit(
            (
                parsed.scheme.lower(),
                netloc,
                path_part if allow_path else "",
                normalized_query,
                "",
            )
        )

    def assert_within_domain_root(self, normalized_url: str, normalized_root: str) -> None:
        url_host = urllib.parse.urlsplit(normalized_url).hostname or ""
        url_parts = urllib.parse.urlsplit(normalized_url)
        root_parts = urllib.parse.urlsplit(normalized_root)
        root_host = root_parts.hostname or ""
        root_path = root_parts.path.rstrip("/") or "/"
        if not (url_host == root_host or url_host.endswith(f".{root_host}")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL is outside the allowed domain root.")
        url_path = url_parts.path.rstrip("/") or "/"
        if not url_path.startswith(root_path):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL is outside the allowed domain root path.")

    def _validate_host(self, hostname: str) -> None:
        lowered = hostname.lower()
        if lowered in BLOCKED_HOSTS or lowered.endswith(".local"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Local or loopback hosts are not allowed.")
        try:
            ip = ipaddress.ip_address(lowered)
        except ValueError:
            self._validate_resolved_addresses(lowered)
            return
        self._assert_public_ip(ip)

    def _validate_resolved_addresses(self, hostname: str) -> None:
        try:
            resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except OSError:
            return
        for _, _, _, _, sockaddr in resolved:
            self._assert_public_ip(ipaddress.ip_address(sockaddr[0]))

    def _assert_public_ip(self, ip: ipaddress._BaseAddress) -> None:
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Private or reserved IP addresses are not allowed.")
