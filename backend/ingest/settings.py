"""Offline configuration; contact is read from the single root .env."""

import os
import re
import tomllib
from pathlib import Path

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def load_settings(path=None):
    path = path or Path(__file__).parent / "config" / "sources.toml"
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    local = dotenv_values(ROOT / ".env")
    config["crawl"]["contact_email"] = os.getenv("INGEST_CONTACT_EMAIL", local.get("INGEST_CONTACT_EMAIL") or "")
    config["data_dir"] = BACKEND / "data"
    if config["crawl"]["min_interval_seconds"] < 1:
        raise ValueError("crawl.min_interval_seconds must be >= 1")
    return config


def user_agent(config):
    email = config["crawl"].get("contact_email", "")
    if not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", email):
        raise ValueError("Set INGEST_CONTACT_EMAIL in root .env before network crawling")
    return f"{config['crawl']['user_agent']} (contact: {email})"
