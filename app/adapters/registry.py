from __future__ import annotations

from adapters.market_x import MarketXAdapter
from adapters.shop_a import ShopAAdapter
from adapters.shop_b import ShopBAdapter
from adapters.shop_c import ShopCAdapter
from adapters.shop_d import ShopDAdapter

ADAPTERS = {
    "shop_a": ShopAAdapter(),
    "shop_b": ShopBAdapter(),
    "shop_c": ShopCAdapter(),
    "shop_d": ShopDAdapter(),
    "market_x": MarketXAdapter(),
}
