from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from fetch.client import FetchResult


class Adapter(ABC):
    key: str

    @abstractmethod
    def iter_listings(self, base_url: str) -> list[dict[str, Any]]:
        ...

    def parse_page(self, result: FetchResult) -> list[dict[str, Any]]:
        if result.page_state != "ok":
            return []
        return self.parse_html(result.text, result.url)

    @abstractmethod
    def parse_html(self, html: str, url: str) -> list[dict[str, Any]]:
        ...
