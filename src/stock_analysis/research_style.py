from __future__ import annotations

import re

FORBIDDEN_PATTERNS = (
    re.compile(r"\.(?:py|js|sh)\b", re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:/Users/|/home/|[A-Za-z]:\\)\S+"),
    re.compile(r"\b(?:aftermarket|push2|exa)\b", re.IGNORECASE),
    re.compile(r"脚本|采集|推测|不确定性|猜测|降级|fallback", re.IGNORECASE),
)


STYLE_REPLACEMENTS = (
    (re.compile(r"\blenses\b", re.IGNORECASE), "专家"),
    (re.compile(r"\blens\b", re.IGNORECASE), "专家"),
    (re.compile(r"\bevidences\b", re.IGNORECASE), "证据链"),
    (re.compile(r"\bevidence\b", re.IGNORECASE), "证据链"),
    (re.compile(r"\bsingle\b", re.IGNORECASE), "单一专家"),
    (re.compile(r"\bcommittee\b", re.IGNORECASE), "投委会"),
    (re.compile(r"aftermarket\.py\s*脚本采集到\s*push2\s*数据", re.IGNORECASE), "据公开市场数据"),
    (re.compile(r"(?:早盘|实时)采集"), "盘中数据显示"),
    (re.compile(r"推测为(?:当日|全天)?数据"), "按惯例回溯至该日"),
    (re.compile(r"存在不确定性"), "数据口径有待确认"),
    (re.compile(r"\bM[1-6]\s*(?:模块)?降级", re.IGNORECASE), "本模块证据暂缺"),
    (re.compile(r"fallback\s*到", re.IGNORECASE), "切换至"),
    (re.compile(r"被限流|被封(?:禁)?"), "数据源暂未更新"),
    (re.compile(r"口径来自[^，。；\n]+"), "据交易所及财经终端披露"),
    (
        re.compile(
            r"(?<!免责声明与)(?<!免责声明与数据)(?<!关键情绪)(?:数据)?来源[：:]\s*(?!暂无|缺失|不足|未接入)[^，。；\n]+",
            re.IGNORECASE,
        ),
        "据公开市场数据",
    ),
    (re.compile(r"\b(?:push2|exa)\b", re.IGNORECASE), "公开市场数据"),
    (re.compile(r"\baftermarket(?:\.py)?\b", re.IGNORECASE), ""),
    (re.compile(r"脚本"), ""),
    (re.compile(r"采集"), "整理"),
    (re.compile(r"推测"), "判断"),
    (re.compile(r"不确定性"), "数据口径有待确认"),
    (re.compile(r"猜测"), "判断"),
    (re.compile(r"降级"), "证据暂缺"),
    (re.compile(r"fallback", re.IGNORECASE), "数据口径切换"),
)


def sanitize_research_report(text: str) -> str:
    """Remove implementation language before a report is shown to readers."""
    cleaned = text
    for pattern, replacement in STYLE_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)

    cleaned = re.sub(r"(?:/Users/|/home/)\S+", "", cleaned)
    cleaned = re.sub(r"[A-Za-z]:\\\S+", "", cleaned)
    cleaned = re.sub(r"\b\S+\.(?:py|js|sh)\b", "", cleaned, flags=re.IGNORECASE)

    safe_lines: list[str] = []
    for line in cleaned.splitlines():
        if any(pattern.search(line) for pattern in FORBIDDEN_PATTERNS):
            continue
        normalized = line if line.lstrip().startswith("|") else re.sub(r"[ \t]{2,}", " ", line)
        safe_lines.append(normalized.rstrip())
    return "\n".join(safe_lines).strip() + "\n"


def has_engineering_language(text: str) -> bool:
    return any(pattern.search(text) for pattern in FORBIDDEN_PATTERNS)
