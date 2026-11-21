"""Параметри магазину: реальні (data/raw/params.json) або приклад із config/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_params() -> dict:
    real = ROOT / "data" / "raw" / "params.json"
    example = ROOT / "config" / "shipping_params.example.json"
    return json.loads((real if real.exists() else example).read_text(encoding="utf-8"))