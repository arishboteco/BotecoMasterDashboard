from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd

import boteco_logger
import database

logger = boteco_logger.get_logger(__name__)

FALLBACK_ALIASES = [
    {"location_id": 2, "alias": "Boteco - Bagmane"},
    {"location_id": 1, "alias": "Boteco - Indiqube"},
    {"location_id": 2, "alias": "Boteco Bagmane"},
    {"location_id": 1, "alias": "Boteco Indiqube"},
    {"location_id": 2, "alias": "Bagmane"},
    {"location_id": 1, "alias": "Indiqube"},
    {"location_id": 1, "alias": "Boteco"},
]


def _norm(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _load_preview_frame(file_content: bytes, filename: str, max_rows: int = 25) -> pd.DataFrame:
    bio = BytesIO(file_content)
    low = filename.lower()
    head = file_content[:2500].lower()
    if low.endswith(".csv"):
        try:
            return pd.read_csv(bio, header=None, nrows=max_rows)
        except Exception:
            bio.seek(0)
            return pd.read_csv(bio, nrows=max_rows)
    if b"<html" in head or b"<!doctype" in head:
        try:
            dfs = pd.read_html(bio)
            return dfs[0].head(max_rows) if dfs else pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    for engine in (None, "openpyxl", "xlrd"):
        try:
            bio.seek(0)
            kwargs = {"engine": engine} if engine else {}
            return pd.read_excel(bio, sheet_name=0, header=None, nrows=max_rows, **kwargs)
        except Exception:
            continue
    return pd.DataFrame()


def _get_aliases() -> List[Dict[str, Any]]:
    try:
        client = database.get_supabase_client() if database.use_supabase() else None
        if client is not None:
            result = (
                client.table("location_aliases")
                .select("location_id, alias")
                .eq("is_active", True)
                .execute()
            )
            rows = result.data or []
            if rows:
                return rows
    except Exception:
        logger.debug("Could not load location_aliases; using fallback aliases.", exc_info=True)
    return FALLBACK_ALIASES


def _match_alias(candidate: str, aliases: List[Dict[str, Any]], exact_only: bool) -> Optional[Dict[str, Any]]:
    candidate_norm = _norm(candidate)
    if not candidate_norm:
        return None
    prepared = sorted(
        [
            {
                "location_id": int(row["location_id"]),
                "alias": str(row["alias"]),
                "norm": _norm(row["alias"]),
            }
            for row in aliases
            if row.get("alias") and row.get("location_id") is not None
        ],
        key=lambda r: len(r["norm"]),
        reverse=True,
    )
    for row in prepared:
        if exact_only and candidate_norm == row["norm"]:
            return {"location_id": row["location_id"], "detected_location_name": row["alias"]}
        if not exact_only and row["norm"] and row["norm"] in candidate_norm:
            return {"location_id": row["location_id"], "detected_location_name": row["alias"]}
    return None


def detect_location_from_file(file_content: bytes, filename: str) -> Optional[Dict[str, Any]]:
    df = _load_preview_frame(file_content, filename)
    if df is None or df.empty:
        return None
    aliases = _get_aliases()
    rows = df.fillna("").astype(str).values.tolist()
    for row in rows:
        for i, cell in enumerate(row):
            if _norm(cell).startswith("restaurant name"):
                for next_cell in row[i + 1 :]:
                    if _norm(next_cell):
                        match = _match_alias(next_cell, aliases, exact_only=True)
                        if match:
                            return match
                        break
    cells = [_norm(cell) for row in rows for cell in row if _norm(cell)]
    for cell in cells:
        match = _match_alias(cell, aliases, exact_only=True)
        if match:
            return match
    joined = " ".join(cells)
    return _match_alias(joined, aliases, exact_only=False)
