"""Vercel serverless entry — read-only dashboard backed by bundled demo DB."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

bundled = ROOT / "data" / "demo_readonly.db"
runtime = Path("/tmp/demo_readonly.db")
if bundled.exists() and not runtime.exists():
    shutil.copy(bundled, runtime)

import os

os.environ.setdefault("DATABASE_URL", f"sqlite:///{runtime}")
os.environ.setdefault("READONLY", "1")

from main import app  # noqa: E402

# Vercel expects `app` callable
handler = app
