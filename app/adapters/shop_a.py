from __future__ import annotations

from selectolax.parser import HTMLParser

from adapters.base import Adapter
from fetch.client import SiteFetcher


class ShopAAdapter(Adapter):
    key = "shop_a"

    def iter_listings(self, base_url: str) -> list[dict]:
        fetcher = SiteFetcher()
        out: list[dict] = []
        page = 1
        while page <= 6:
            url = f"{base_url}/shop-a/page/{page}" if page > 1 else f"{base_url}/shop-a/"
            res = fetcher.fetch(url)
            if res.page_state != "ok":
                break
            batch = self.parse_html(res.text, url)
            if not batch:
                break
            for row in batch:
                row["page_state"] = res.page_state
                row["snapshot_hash"] = res.snapshot_hash
            out.extend(batch)
            page += 1
        return out

    def parse_html(self, html: str, url: str) -> list[dict]:
        tree = HTMLParser(html)
        rows = []
        for li in tree.css("li.product"):
            sku = li.attributes.get("data-sku", "")
            rows.append(
                {
                    "url": url + "#" + sku,
                    "raw_title": li.css_first(".title").text(strip=True) if li.css_first(".title") else "",
                    "price": float(li.css_first(".price").text(strip=True).replace("$", "")) if li.css_first(".price") else None,
                    "shipping": float(li.css_first(".shipping").text(strip=True).replace("$", "")) if li.css_first(".shipping") else 0.0,
                    "in_stock": "out" not in (li.css_first(".stock").text(strip=True).lower() if li.css_first(".stock") else "in"),
                    "gtin": li.attributes.get("data-gtin"),
                    "mpn": li.attributes.get("data-mpn"),
                    "pack_size": int(li.css_first(".pack-size").text(strip=True)) if li.css_first(".pack-size") else 1,
                    "seller": "Shop A",
                    "condition": "new",
                    "parse_confidence": 1.0,
                }
            )
        return rows
