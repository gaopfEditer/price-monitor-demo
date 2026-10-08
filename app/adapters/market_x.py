from __future__ import annotations

import httpx

from adapters.base import Adapter


class MarketXAdapter(Adapter):
    key = "market_x"

    def iter_listings(self, base_url: str) -> list[dict]:
        out: list[dict] = []
        with httpx.Client(timeout=30) as client:
            for page in range(1, 6):
                r = client.get(f"{base_url}/market-x/listings", params={"page": page})
                data = r.json()
                listings = data.get("listings") or []
                if not listings:
                    break
                for L in listings:
                    out.append(
                        {
                            "url": f"{base_url}/market-x/listings#{L['sku']}-{L.get('seller','')}",
                            "raw_title": L.get("title", ""),
                            "brand": L.get("brand"),
                            "model": L.get("model"),
                            "gtin": L.get("gtin"),
                            "mpn": L.get("mpn"),
                            "price": L.get("price"),
                            "shipping": L.get("shipping", 0),
                            "landed_price": L.get("landed_price"),
                            "in_stock": L.get("in_stock", True),
                            "pack_size": L.get("pack_size", 1),
                            "seller": L.get("seller", "Market Seller"),
                            "condition": L.get("condition", "new"),
                            "parse_confidence": 1.0,
                            "page_state": "ok",
                            "snapshot_hash": "market-json",
                        }
                    )
        return out

    def parse_html(self, html: str, url: str) -> list[dict]:
        return []
