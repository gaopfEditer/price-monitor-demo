from __future__ import annotations

from selectolax.parser import HTMLParser

from adapters.base import Adapter
from fetch.client import SiteFetcher


class ShopDAdapter(Adapter):
    key = "shop_d"

    def iter_listings(self, base_url: str) -> list[dict]:
        fetcher = SiteFetcher()
        out: list[dict] = []
        for page in range(1, 4):
            url = f"{base_url}/shop-d/page/{page}"
            res = fetcher.fetch(url)
            if res.page_state != "ok":
                out.append({"url": url, "page_state": res.page_state, "parse_confidence": 0.0, "meta_only": True})
                continue
            batch = self.parse_html(res.text, url)
            for row in batch:
                row["page_state"] = res.page_state
                row["snapshot_hash"] = res.snapshot_hash
            out.extend(batch)
        return out

    def parse_html(self, html: str, url: str) -> list[dict]:
        tree = HTMLParser(html)
        rows: list[dict] = []
        # v0 selectors
        for div in tree.css("div.item"):
            sku = div.attributes.get("data-id", "")
            cost = div.css_first(".cost")
            name = div.css_first(".name")
            avail = div.css_first(".availability")
            if cost and name:
                rows.append(self._row(sku, name.text(strip=True), cost.text(strip=True), avail.text(strip=True) if avail else "True", url))
        # v1 selectors fallback
        for art in tree.css("article"):
            sku = art.attributes.get("data-product-sku", "")
            pt = art.css_first(".price-tag")
            header = art.css_first("header")
            stock = art.css_first(".stock-flag")
            if pt and header:
                price_txt = pt.attributes.get("value") or pt.text(strip=True).replace("$", "")
                in_stock = (stock.attributes.get("value") if stock else "yes") == "yes"
                rows.append(
                    {
                        "url": url + "#" + sku,
                        "raw_title": header.text(strip=True),
                        "price": float(str(price_txt).replace("$", "")),
                        "shipping": 6.0,
                        "in_stock": in_stock,
                        "parse_confidence": 0.85,
                        "seller": "Shop D",
                        "condition": "new",
                    }
                )
        return rows

    def _row(self, sku: str, title: str, price: str, avail: str, url: str) -> dict:
        return {
            "url": url + "#" + sku,
            "raw_title": title,
            "price": float(price.replace("$", "")),
            "shipping": 6.0,
            "in_stock": avail.lower() in ("true", "1", "yes", "in stock"),
            "parse_confidence": 0.9,
            "seller": "Shop D",
            "condition": "new",
        }
