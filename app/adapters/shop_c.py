from __future__ import annotations

from selectolax.parser import HTMLParser

from adapters.base import Adapter
from fetch.client import SiteFetcher


class ShopCAdapter(Adapter):
    key = "shop_c"

    def iter_listings(self, base_url: str) -> list[dict]:
        fetcher = SiteFetcher(min_interval=0.01)
        out: list[dict] = []
        for page in range(1, 4):
            url = f"{base_url}/shop-c/page/{page}"
            res = fetcher.fetch(url)
            if res.page_state in ("challenge", "rate_limited", "empty", "parse_fail"):
                out.append(
                    {
                        "url": url,
                        "raw_title": "",
                        "price": None,
                        "shipping": 0,
                        "in_stock": False,
                        "page_state": res.page_state,
                        "snapshot_hash": res.snapshot_hash,
                        "parse_confidence": 0.0,
                        "seller": "Shop C",
                        "condition": "new",
                        "meta_only": True,
                    }
                )
                continue
            batch = self.parse_html(res.text, url)
            for row in batch:
                row["page_state"] = res.page_state
                row["snapshot_hash"] = res.snapshot_hash
            out.extend(batch)
        return out

    def parse_html(self, html: str, url: str) -> list[dict]:
        tree = HTMLParser(html)
        rows = []
        for li in tree.css("li"):
            sku = li.attributes.get("data-sku", url)
            price_el = li.css_first(".amount")
            rows.append(
                {
                    "url": url + "#" + sku,
                    "raw_title": li.css_first(".product-name").text(strip=True) if li.css_first(".product-name") else "",
                    "price": float(price_el.text(strip=True).replace("$", "")) if price_el else None,
                    "shipping": 8.0,
                    "in_stock": True,
                    "parse_confidence": 0.95,
                    "seller": "Shop C",
                    "condition": "new",
                }
            )
        return rows
