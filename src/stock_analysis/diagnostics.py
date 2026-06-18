from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

import requests

from .config import SourceConfig
from .http import em_get, force_cn_encoding


@dataclass
class DiagnosticItem:
    name: str
    status: str
    detail: str


def _direct_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def run_diagnostics(config: SourceConfig) -> list[DiagnosticItem]:
    items = [
        diagnose_tencent(),
        diagnose_sina(),
        diagnose_camofox(config),
        diagnose_hermes_browser(),
        diagnose_playwright(),
        diagnose_eastmoney(config),
        diagnose_mootdx(config),
    ]
    return items


def diagnose_camofox(config: SourceConfig) -> DiagnosticItem:
    try:
        response = _direct_session().get(
            config.camofox_health_url,
            timeout=config.camofox_timeout_seconds,
        )
        if response.ok:
            return DiagnosticItem("browser.camofox", "ok", "camofox-browser 可用")
    except Exception:
        pass
    return DiagnosticItem(
        "browser.camofox",
        "warn",
        "3 秒内未响应；下一步由 Agent 接管 Hermes browser，或尝试本地 Playwright",
    )


def diagnose_eastmoney(config: SourceConfig) -> DiagnosticItem:
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    try:
        response = em_get(url, timeout=5)
        if response.ok:
            return DiagnosticItem("eastmoney.http", "ok", "东财接口可访问；仍需遵守串行限流")
    except Exception:
        pass
    return DiagnosticItem("eastmoney.http", "warn", "东财接口不可达或疑似风控；建议重试或更换网络")


def diagnose_tencent() -> DiagnosticItem:
    try:
        response = _direct_session().get("https://qt.gtimg.cn/q=sh000001", timeout=5)
        force_cn_encoding(response)
        if response.ok and "v_sh000001" in response.text:
            return DiagnosticItem("tencent.quote", "ok", "腾讯行情可访问，GB2312 解码正常")
    except Exception:
        pass
    return DiagnosticItem("tencent.quote", "warn", "腾讯行情不可达，主行情将切换至新浪")


def diagnose_sina() -> DiagnosticItem:
    try:
        response = _direct_session().get(
            "https://hq.sinajs.cn/list=s_sh000001",
            headers={"Referer": "https://finance.sina.com.cn/"},
            timeout=5,
        )
        force_cn_encoding(response)
        if response.ok and "hq_str_s_sh000001" in response.text:
            return DiagnosticItem("sina.quote", "ok", "新浪行情可访问，GB2312 解码正常")
    except Exception:
        pass
    return DiagnosticItem("sina.quote", "warn", "新浪行情不可达，将继续使用腾讯或东财备用源")


def diagnose_hermes_browser() -> DiagnosticItem:
    return DiagnosticItem(
        "browser.hermes",
        "info",
        "Hermes 内置浏览器属于 Agent 工具；CLI 无法直接探测，API/Camofox 失败时需由 Agent 接管",
    )


def diagnose_playwright() -> DiagnosticItem:
    if shutil.which("playwright") or importlib.util.find_spec("playwright"):
        return DiagnosticItem("browser.playwright", "ok", "Playwright 可用")
    return DiagnosticItem("browser.playwright", "warn", "Playwright 未安装，浏览器末级 fallback 不可用")


def diagnose_mootdx(config: SourceConfig) -> DiagnosticItem:
    if not config.enable_mootdx:
        return DiagnosticItem("mootdx", "info", "当前默认禁用 mootdx，以提升稳定性")
    if importlib.util.find_spec("mootdx") is None:
        return DiagnosticItem("mootdx", "warn", "已请求启用 mootdx，但依赖未安装")
    return DiagnosticItem("mootdx", "info", "mootdx 已安装；TCP 连通性需在实际五档/逐笔请求时确认")
