from __future__ import annotations

from dataclasses import dataclass

MOOTDX_REQUEST_TYPES = {"order_book", "transactions", "minute_kline", "deep_kline", "extended_quote"}


@dataclass
class RouteDecision:
    chain: list[str]
    browser_required: bool = False
    reason: str = ""


def needs_mootdx(request_type: str | None) -> bool:
    return request_type in MOOTDX_REQUEST_TYPES


def build_quote_route(
    market: str,
    asset_type: str = "stock",
    require_depth: bool = False,
    request_type: str | None = None,
) -> RouteDecision:
    if asset_type == "fund":
        return RouteDecision(
            chain=["eastmoney-fund", "sina-fund", "eastmoney-browser"],
            browser_required=False,
            reason="基金持仓优先天天基金/东财基金估值，新浪基金为第一 fallback",
        )
    if market == "a":
        chain = ["tencent-quote", "sina-quote"]
        if require_depth or needs_mootdx(request_type):
            chain.append("mootdx-depth")
        chain.extend(["eastmoney-stock-get", "browser-fallback"])
        return RouteDecision(chain=chain, browser_required=True, reason="A股主路径：腾讯/新浪")
    if market == "hk":
        return RouteDecision(
            chain=["tencent-hk", "sina-hk", "eastmoney-hk", "browser-fallback"],
            browser_required=True,
            reason="港股主路径：腾讯港股接口，新浪/东财逐级 fallback",
        )
    if market == "us":
        return RouteDecision(
            chain=["tencent-us", "sina-us", "eastmoney-us", "browser-fallback"],
            browser_required=True,
            reason="美股主路径：腾讯美股接口，新浪为第一 fallback",
        )
    if market == "jp":
        return RouteDecision(
            chain=["yahoo-chart", "last-success-cache"],
            reason="日本免登录日线为 Yahoo 单源；缓存只作故障恢复，不作独立交叉验证",
        )
    if market == "kr":
        return RouteDecision(
            chain=["naver-chart", "yahoo-chart", "last-success-cache"],
            reason="韩国日线优先 Naver，并用 Yahoo 做逐字段交叉验证",
        )
    return RouteDecision(chain=["browser-fallback"], browser_required=True, reason="未知市场仅保留浏览器降级")
