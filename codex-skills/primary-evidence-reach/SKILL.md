---
name: primary-evidence-reach
description: 补齐 stock-analysis Company Evidence 中缺少的发行人一手财务、经营、治理、风险或公告证据；适用于 A/HK/US/JP/KR 股票出现 agent_primary_evidence_reach=recommended，或用户明确要求补齐一手证据时。
---

# Primary Evidence Reach

先运行 stock-analysis 的确定性入口。只有 Evidence Pack 的
`_meta.source_events` 明确出现 `agent_primary_evidence_reach=recommended`，或用户明确要求补齐一手披露时，才执行本 Skill。

## 获取顺序

1. 若环境中已经存在 `agent-reach`，先读取并遵循它的 `SKILL.md`，使用其网页/GitHub 搜索与网页阅读路由。
2. 若不存在 `agent-reach`，直接使用宿主 Agent 已有的官方网页搜索、浏览器和 PDF 阅读能力；不得要求用户预先安装额外 Skill。
3. 按 Evidence Pack 的 `_meta.primary_evidence_requests` 逐模块检索，不做无目标的泛搜。
4. A股依次搜索：公司 IR、巨潮资讯、上交所/深交所；港股依次搜索 HKEXnews、公司 IR。
5. 美股依次搜索 SEC EDGAR、公司 IR；日本依次搜索公司 IR、JPX、TDnet、EDINET；韩国依次搜索公司 IR、DART、KIND。
6. Yahoo、Naver、WiseReport、新闻、搜索摘要只能定位原文，不能写成 issuer-primary evidence。

## 证据门禁

- 原文 URL 必须是 HTTPS，并直接指向发行人、交易所或监管机构页面/PDF。
- `published_at` 不得晚于研究日期；报告期不能代替发布日期。
- 每个数值记录报告期、币种/单位、合并或单体口径、原文页码或定位说明。
- 搜索摘要、模型推断和二手转述不能进入输出 JSON。
- 找不到原文时停止补齐，保留原 Evidence Gap。

## 输出契约

把核验结果保存为用户工作区中的 JSON，然后重新运行：

```bash
stock-analysis --market research --symbol <symbol> \
  --primary-evidence-file /absolute/path/primary-evidence.json
```

JSON 最小格式：

```json
{
  "schema_version": "1.0",
  "symbol": "7203.T",
  "retrieval_method": "agent-reach-or-host-web",
  "items": [
    {
      "module": "C2",
      "metric": "revenue",
      "period": "2026FY",
      "value": 123456,
      "currency": "JPY",
      "source": "issuer annual report",
      "url": "https://issuer.example/annual-report.pdf",
      "published_at": "2026-05-01",
      "page": 1,
      "extraction_note": "consolidated statement; unit JPY million"
    }
  ]
}
```

示例数值仅展示字段类型；实际原文没有数值时不得写零。Python 门禁会校验 symbol、HTTPS URL、发布日期截止和必要字段；导入项仍保持 `conditional`，直到目录化解析器或人工复核进一步确认。
