from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PRESETS_DIR = Path(os.getenv("PRESETS_DIR", BASE_DIR.parent / "presets"))
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", BASE_DIR / "config"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR.parent / 'data' / 'app.db'}")
SANDBOX_BASE_URL = os.getenv("SANDBOX_BASE_URL", "http://localhost:8001")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"
SNAPSHOT_DIR = Path(os.getenv("SNAPSHOT_DIR", BASE_DIR.parent / "data" / "snapshots"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR.parent / "data" / "evidence"))

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Diff / alert defaults
PRICE_ABS_MIN = float(os.getenv("PRICE_ABS_MIN", "1.0"))
PRICE_PCT_MIN = float(os.getenv("PRICE_PCT_MIN", "3.0"))
CONFIRM_STREAK = int(os.getenv("CONFIRM_STREAK", "2"))
EVENT_COOLDOWN_HOURS = int(os.getenv("EVENT_COOLDOWN_HOURS", "6"))
MATCH_AUTO_THRESHOLD = float(os.getenv("MATCH_AUTO_THRESHOLD", "0.8"))
MAP_CONFIRM_STREAK = int(os.getenv("MAP_CONFIRM_STREAK", "2"))
