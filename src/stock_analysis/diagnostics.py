from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import SourceConfig


@dataclass
class DiagnosticItem:
    name: str
    status: str
    detail: str


def run_diagnostics(config: SourceConfig) -> list[DiagnosticItem]:
    items = [
        diagnose_camofox(config),
        diagnose_eastmoney(config),
        diagnose_mootdx(config),
    ]
    return items


def diagnose_camofox(config: SourceConfig) -> DiagnosticItem:
    try:
        response = requests.get(config.camofox_health_url, timeout=config.camofox_timeout_seconds)
        if response.ok:
            return DiagnosticItem("browser.camofox", "ok", "camofox-browser 可用")
    except Exception:
        pass
    return DiagnosticItem("browser.camofox", "warn", "3 秒内未响应，将自动降级到 Hermes 内置浏览器或 Playwright")


def diagnose_eastmoney(config: SourceConfig) -> DiagnosticItem:
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    try:
        response = requests.get(url, timeout=5)
        if response.ok:
            return DiagnosticItem("eastmoney.http", "ok", "东财接口可访问；仍需遵守串行限流")
    except Exception:
        pass
    return DiagnosticItem("eastmoney.http", "warn", "东财接口不可达或疑似风控；建议重试或更换网络")


def diagnose_mootdx(config: SourceConfig) -> DiagnosticItem:
    if not config.enable_mootdx:
        return DiagnosticItem("mootdx", "info", "当前默认禁用 mootdx，以提升稳定性")
    return DiagnosticItem("mootdx", "warn", "已启用 mootdx；海外或不稳定网络可能需要改走腾讯/新浪")
