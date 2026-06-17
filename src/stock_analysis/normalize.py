from __future__ import annotations

import re


def normalize_code(symbol: str, source: str = "generic") -> str:
    value = symbol.strip()
    upper = value.upper()
    lower = value.lower()

    if lower.startswith("gb_"):
        return upper[3:]
    if lower.startswith("us"):
        return upper[2:]
    if lower.startswith("fu"):
        return re.sub(r"\D", "", value)
    if lower.startswith("hk"):
        digits = re.sub(r"\D", "", value)
        return f"{digits[-4:].zfill(4)}.HK"
    if upper.endswith(".HK"):
        digits = re.sub(r"\D", "", upper.split(".")[0])
        return f"{digits[-4:].zfill(4)}.HK"
    if upper.endswith(".SH") or upper.endswith(".SZ"):
        return re.sub(r"\D", "", upper.split(".")[0])[-6:]
    if lower.startswith(("sh", "sz", "bj")):
        return re.sub(r"\D", "", value)[-6:]
    if re.fullmatch(r"\d{6}", value):
        return value
    return upper
