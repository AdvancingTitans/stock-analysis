from __future__ import annotations

import random
import time
from typing import Any

import requests

DEFAULT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": DEFAULT_UA})
EM_SESSION.trust_env = False
_last_eastmoney_call = [0.0]


def force_cn_encoding(response: requests.Response) -> requests.Response:
    response.encoding = "gb2312"
    return response


def safe_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def em_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    min_interval: float = 1.0,
    retries: int = 3,
    timeout: float = 15.0,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(retries):
        wait = min_interval - (time.time() - _last_eastmoney_call[0])
        if wait > 0:
            time.sleep(wait + random.uniform(0.1, 0.4))
        try:
            response = EM_SESSION.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep((2**attempt) + random.uniform(0.1, 0.5))
        finally:
            _last_eastmoney_call[0] = time.time()
    raise RuntimeError(f"eastmoney request failed after retries: {url}") from last_error
