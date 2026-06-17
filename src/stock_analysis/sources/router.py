from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RouteDecision:
    chain: list[str]
    browser_required: bool = False
    reason: str = ""


def build_quote_route(market: str, asset_type: str = "stock", require_depth: bool = False) -> RouteDecision:
    if asset_type == "fund":
        return RouteDecision(
            chain=["eastmoney-fund", "sina-fund", "eastmoney-browser"],
            browser_required=False,
            reason="基金持仓优先天天基金/东财基金估值，新浪基金为第一 fallback",
        )
    if market == "a":
        chain = ["tencent-quote", "sina-quote"]
        if require_depth:
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
    return RouteDecision(chain=["browser-fallback"], browser_required=True, reason="未知市场仅保留浏览器降级")
