"""Map Cashfree registry API payloads into onboarding-friendly shapes."""

from __future__ import annotations

import re
from typing import Any


def parse_pan_doi(raw: str) -> str:
    """Convert PAN 360 DOB (DD-MM-YYYY) or ISO date to YYYY-MM-DD."""
    value = (raw or "").strip()
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    match = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", value)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return value[:10]


def parse_gst_address(address: str) -> dict[str, str]:
    """Best-effort split of GST principal place string."""
    text = (address or "").strip()
    if not text:
        return {"line1": "", "line2": "", "city": "", "state": "", "pin": ""}
    parts = [part.strip() for part in text.split(",") if part.strip()]
    pin = ""
    state = ""
    city = ""
    if parts and re.fullmatch(r"\d{6}", parts[-1]):
        pin = parts.pop()
    if parts:
        state = parts.pop()
    if parts:
        city = parts.pop()
    line1 = ", ".join(parts) if parts else text
    return {"line1": line1, "line2": "", "city": city, "state": state, "pin": pin}


def pan_address_block(data: dict[str, Any]) -> dict[str, str]:
    address = data.get("address") or {}
    if isinstance(address, dict):
        pin = str(address.get("pincode") or address.get("pin") or "")
        return {
            "line1": str(address.get("full_address") or address.get("street") or "")[:200],
            "line2": "",
            "city": str(address.get("city") or "")[:80],
            "state": str(address.get("state") or "")[:80],
            "pin": pin[:6],
        }
    return {"line1": "", "line2": "", "city": "", "state": "", "pin": ""}


def udyam_address_block(data: dict[str, Any]) -> dict[str, str]:
    """Map Cashfree Udyam split_address into onboarding Address shape."""
    split = data.get("split_address") or {}
    if not isinstance(split, dict):
        return {"line1": "", "line2": "", "city": "", "state": "", "pin": ""}
    parts = [
        str(split.get("flat") or "").strip(),
        str(split.get("building") or "").strip(),
        str(split.get("street") or "").strip(),
        str(split.get("village") or "").strip(),
        str(split.get("block") or "").strip(),
    ]
    line1 = ", ".join(part for part in parts if part)
    return {
        "line1": line1[:200],
        "line2": "",
        "city": str(split.get("city") or split.get("district") or "")[:80],
        "state": str(split.get("state") or "")[:80],
        "pin": str(split.get("pincode") or "")[:6],
    }


def registered_address_from_cin(data: dict[str, Any]) -> dict[str, str]:
    """Best-effort registered office from CIN payload (director address on MCA record)."""
    for key in (
        "registered_office_address",
        "registered_address",
        "company_address",
        "registered_office",
        "address",
    ):
        raw = data.get(key)
        if isinstance(raw, str) and raw.strip():
            return parse_gst_address(raw)
        if isinstance(raw, dict):
            return pan_address_block({"address": raw})
    for item in data.get("director_details") or []:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("address") or "").strip()
        if raw:
            return parse_gst_address(raw)
    return {"line1": "", "line2": "", "city": "", "state": "", "pin": ""}


def directors_from_cin(data: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for item in data.get("director_details") or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "din": str(item.get("din") or "")[:20],
                "designation": (item.get("designation") or "Director").strip()[:80],
                "dob": parse_pan_doi(str(item.get("dob") or "")),
                "address": str(item.get("address") or "")[:200],
                "pan": "",
            }
        )
    return rows
