from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

CHALLENGE_TITLES = ("just a moment", "security check", "attention required")
CHALLENGE_KEYWORDS = ("cf-challenge", "cloudflare", "captcha", "challenge-page")


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    page_state: str  # ok | challenge | empty | rate_limited | parse_fail
    snapshot_hash: str
    retry_after: Optional[int] = None


class SiteFetcher:
    """Per-host token bucket + exponential backoff (demo-friendly)."""

    def __init__(self, min_interval: float = 0.05):
        self.min_interval = min_interval
        self._last: dict[str, float] = {}

    def _wait(self, host: str) -> None:
        now = time.time()
        last = self._last.get(host, 0.0)
        delta = now - last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last[host] = time.time()

    def fetch(self, url: str, timeout: float = 30.0) -> FetchResult:
        host = httpx.URL(url).host or "localhost"
        self._wait(host)
        attempt = 0
        while attempt < 4:
            attempt += 1
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": "RetailMAPWatchDemo/1.0 (+sandbox)"})
            except httpx.HTTPError as exc:
                if attempt >= 4:
                    return FetchResult(url, 0, "", "parse_fail", "", None)
                time.sleep(2 ** attempt * 0.2)
                continue

            text = resp.text or ""
            h = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
            if resp.status_code == 429:
                ra = int(resp.headers.get("Retry-After", "30"))
                return FetchResult(url, 429, text, "rate_limited", h, ra)
            state = detect_page_state(resp.status_code, text)
            if state == "ok" or attempt >= 4:
                return FetchResult(url, resp.status_code, text, state, h, None)
            time.sleep(2 ** attempt * 0.2)
        return FetchResult(url, 0, "", "parse_fail", "", None)


def detect_page_state(status_code: int, html: str) -> str:
    """Identify challenge/empty pages — never treat as price changes."""
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500 and status_code != 503:
        return "parse_fail"
    lower = html.lower()
    title_m = re.search(r"<title[^>]*>([^<]+)</title>", lower, re.I)
    title = title_m.group(1).strip() if title_m else ""
    if any(t in title for t in CHALLENGE_TITLES):
        return "challenge"
    if any(k in lower for k in CHALLENGE_KEYWORDS):
        return "challenge"
    if len(html.strip()) < 120:
        return "empty"
    # Heuristic: product-like markers missing on long pages
    if len(html) > 800 and not re.search(r"(price|product|sku|\$)", lower):
        return "parse_fail"
    return "ok"
