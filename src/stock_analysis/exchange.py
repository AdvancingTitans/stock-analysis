from __future__ import annotations

import re

import requests

from .http import force_cn_encoding


def fetch_cny_rates() -> dict[str, float]:
    url = "https://hq.sinajs.cn/list=fx_susdcny,fx_shkdcny"
    response = requests.get(
        url,
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    force_cn_encoding(response)
    rates = {"CNY": 1.0}
    for line in response.text.splitlines():
        m = re.search(r'var hq_str_([^=]+)="([^"]*)"', line)
        if not m:
            continue
        code, payload = m.group(1), m.group(2)
        fields = payload.split(",")
        if len(fields) < 2:
            continue
        try:
            price = float(fields[1])
        except ValueError:
            continue
        if code == "fx_susdcny":
            rates["USD"] = price
        elif code == "fx_shkdcny":
            rates["HKD"] = price
    if "USD" not in rates:
        rates["USD"] = 7.0
    if "HKD" not in rates:
        rates["HKD"] = 0.9
    return rates
