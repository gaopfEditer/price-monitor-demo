from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

DEMO_DB = ROOT / "data" / "demo_readonly.db"


@pytest.fixture()
def demo_client(monkeypatch):
    if not DEMO_DB.is_file():
        pytest.skip("demo_readonly.db not present; run scripts/demo.py")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{DEMO_DB}")
    monkeypatch.setenv("READONLY", "1")
    from importlib import reload

    import config
    import database
    import main

    reload(config)
    reload(database)
    reload(main)
    return TestClient(main.app)


def test_match_queue_no_duplicate_rows(demo_client: TestClient):
    html = demo_client.get("/match-queue").text
    compare_count = html.count('class="compare"')
    if compare_count == 0:
        assert "No pending matches" in html
        return
    keys = re.findall(
        r"<strong>Listing</strong><br/>(.*?)<br/>pack .*?"
        r"<strong>Candidate product</strong><br/>(.*?)<br/>pack",
        html,
        flags=re.S,
    )
    assert len(keys) == compare_count
    assert len(keys) == len(set(keys)), f"duplicate match-queue rows: {keys}"


def test_map_board_no_duplicate_rows(demo_client: TestClient):
    html = demo_client.get("/map").text
    cards = re.findall(r"<article class=\"card\">(.*?)</article>", html, flags=re.S)
    keys = []
    for card in cards:
        title_m = re.search(r"<h3>(.*?)</h3>", card, re.S)
        seller_m = re.search(r"Seller: (.*?) ·", card)
        keys.append((title_m.group(1).strip() if title_m else "", seller_m.group(1).strip() if seller_m else ""))
    assert len(keys) == len(set(keys)), f"duplicate MAP board rows: {keys}"


def test_rendered_html_has_no_absolute_paths(demo_client: TestClient):
    for path in ("/map", "/match-queue", "/"):
        html = demo_client.get(path).text
        assert "/workspace/" not in html
        assert re.search(r"Evidence:\s*<code>/", html) is None
        assert re.search(r'href="/workspace/', html) is None


def test_map_evidence_links_use_relative_route(demo_client: TestClient):
    html = demo_client.get("/map").text
    for href in re.findall(r'href="(/evidence/[^"]+)"', html):
        assert demo_client.get(href).status_code == 200
        assert "/workspace" not in demo_client.get(href).text
