from __future__ import annotations

import httpx

from adapters.base import Adapter


class ShopBAdapter(Adapter):
    key = "shop_b"

    def iter_listings(self, base_url: str) -> list[dict]:
        out: list[dict] = []
        page = 1
        with httpx.Client(timeout=30) as client:
            while page <= 6:
                r = client.get(f"{base_url}/shop-b/api/products", params={"page": page})
                if r.status_code != 200:
                    break
                data = r.json()
                products = data.get("products") or []
                if not products:
                    break
                for p in products:
                    out.append(
                        {
                            "url": f"{base_url}/shop-b/api/products#{p['id']}",
                            "raw_title": p["name"],
                            "brand": p.get("brand"),
                            "model": p.get("model"),
                            "gtin": p.get("gtin"),
                            "mpn": p.get("mpn"),
                            "price": p.get("price"),
                            "shipping": p.get("shipping", 0),
                            "in_stock": p.get("inStock", True),
                            "pack_size": p.get("packSize", 1),
                            "seller": "Shop B",
                            "condition": "new",
                            "parse_confidence": 1.0,
                            "page_state": "ok",
                            "snapshot_hash": "json-api",
                        }
                    )
                page += 1
        return out

    def parse_html(self, html: str, url: str) -> list[dict]:
        return []
