"""Synthetic coffee-equipment catalog for offline demo (not real products)."""
from __future__ import annotations

import json
import random
from pathlib import Path

BRANDS = [
    "SandboxRoast",
    "DemoGrind Co",
    "FictionalBrew",
    "SampleEspresso",
    "MockBean Labs",
]
MODEL_PREFIX = ["SB", "DG", "FB", "SE", "MB"]


def _gtin(seed: int) -> str:
    base = f"088999{seed:06d}"
    digits = [int(c) for c in base]
    total = sum(d if i % 2 == 0 else d * 3 for i, d in enumerate(digits))
    check = (10 - (total % 10)) % 10
    return base + str(check)


def build_catalog(count: int = 60) -> list[dict]:
    rng = random.Random(42)
    products: list[dict] = []
    for i in range(count):
        brand = BRANDS[i % len(BRANDS)]
        prefix = MODEL_PREFIX[i % len(MODEL_PREFIX)]
        model = f"{prefix}{100 + i}"
        pack = 1 if i % 7 != 3 else 2
        title = f"{brand} {model} Home Espresso Machine"
        if pack == 2:
            title = f"{brand} {model} Grinder Burr Set (2-Pack)"
        base = round(rng.uniform(89, 899), 2)
        products.append(
            {
                "sku": f"SKU-{i+1:03d}",
                "title": title,
                "brand": brand,
                "model": model,
                "gtin": _gtin(i + 1),
                "mpn": f"{prefix}-{model}",
                "pack_size": pack,
                "capacity_ml": 250 if i % 5 == 0 else None,
                "color": ["Black", "Silver", "White"][i % 3],
                "base_price": base,
                "map_price": round(base * 0.92, 2),
                "category": ["machine", "grinder", "accessory"][i % 3],
            }
        )
    return products


def save_catalog(path: Path, count: int = 60) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_catalog(count), indent=2))


def load_catalog(path: Path) -> list[dict]:
    if not path.exists():
        save_catalog(path)
    return json.loads(path.read_text())


if __name__ == "__main__":
    out = Path(__file__).parent / "data" / "catalog.json"
    if len(__import__("sys").argv) > 1:
        out = Path(__import__("sys").argv[1])
    save_catalog(out)
    print(f"wrote {out}")
