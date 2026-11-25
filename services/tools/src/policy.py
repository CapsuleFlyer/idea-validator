"""M5 fetch policy: the rules a URL must pass before anything is fetched. No I/O, easy to test."""
from ipaddress import ip_address
from urllib.parse import urlsplit


def parse_allow_list(raw: str) -> frozenset[str]:
    return frozenset(d.strip().lower() for d in raw.split(",") if d.strip())


def check_url(url: str, allowed: frozenset[str]) -> tuple[bool, str]:
    """Return (allowed, reason). https only, no credentials, no IP literals, host on the allow-list."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return False, "malformed url"
    if parts.scheme != "https":
        return False, "only https is allowed"
    if parts.username or parts.password:
        return False, "credentials in url are not allowed"
    if not host:
        return False, "missing host"
    try:
        ip_address(host)
        return False, "ip literals are not allowed"
    except ValueError:
        pass
    if port not in (None, 443):
        return False, "non-standard port"
    if not any(host == d or host.endswith("." + d) for d in allowed):
        return False, f"host '{host}' is not on the allow-list"
    return True, "ok"
