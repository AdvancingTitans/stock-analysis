# 手工取数 fallback 食谱

本文件记录当 `stock_analysis` CLI/Python 模块不可用时，如何手工获取盘后复盘所需的核心 evidence。

## 适用场景

- `uv run python -m stock_analysis` 返回 `No module named stock_analysis`
- 东财 `clist`/资金接口在本地网络空响应或超时
- 需要快速生成 Buffett 等 single-lens 盘后报告

## A股主要指数

腾讯行情接口（GB2312）：

```bash
curl -s 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000300,sh000016' \
  | iconv -f gb2312 -t utf-8
```

字段索引（实测）：

| 索引 | 字段 |
|---:|---|
| 3 | 当前价 |
| 4 | 昨收 |
| 31 | 涨跌额 |
| 32 | 涨跌幅 |
| 37 | 成交额（注意单位） |

## 港股行情

新浪行情接口（GB2312）：

```bash
curl -s 'https://hq.sinajs.cn/list=hkHSI,hkHSCEI,hkHSTECH' \
  -H 'Referer: https://finance.sina.com.cn' \
  | iconv -f gb2312 -t utf-8
```

## 美股行情

新浪行情接口（GB2312）：

```bash
curl -s 'https://hq.sinajs.cn/list=gb_dji,gb_ixic,gb_inx,hf_GC,hf_CL' \
  -H 'Referer: https://finance.sina.com.cn' \
  | iconv -f gb2312 -t utf-8
```

注意：美股在独立日等假期可能提前休市，返回时间戳可能是前一个交易日收盘。

## A股行业板块榜（东财不可用时）

同花顺行业榜公开页面：

```text
https://q.10jqka.com.cn/thshy/
```

浏览器控制台提取表格数据：

```javascript
(() => {
  const rows = Array.from(document.querySelectorAll('table tr'))
    .slice(2)
    .map(r => Array.from(r.querySelectorAll('td'))
      .map(c => c.textContent.trim().replace(/,/g, '')))
    .filter(r => r.length >= 8 && !isNaN(parseFloat(r[2])));
  return {
    total: rows.length,
    max: Math.max(...rows.map(r => parseFloat(r[2]))),
    min: Math.min(...rows.map(r => parseFloat(r[2]))),
    negativeCount: rows.filter(r => parseFloat(r[2]) < 0).length,
    top10: rows.slice().sort((a, b) => parseFloat(b[2]) - parseFloat(a[2])).slice(0, 10)
  };
})()
```

**重要口径提示**：该页面默认只展示涨幅靠前的行业样本，未展示的行业不代表下跌；报告表述应为“收录的 N 个行业全部上涨”或“领涨行业为……”，不得推断为全市场所有行业普涨。

## 蓝筹样本快速报价

腾讯批量接口：

```bash
curl -s 'https://qt.gtimg.cn/q=sh600519,sz000858,sh600036,sh601318,sh600900,sh601088,sz300750,sz002594' \
  | iconv -f gb2312 -t utf-8
```

## Buffett lens 下的数据缺口处理

- 北向资金、精确涨跌家数等短线证据缺失时，不估算、不编造。
- 在 M1/M2/M3 章节明确标注“数据暂缺”，并将判断重心转移到 M4/M5/M6（护城河、安全边际、抗跌方向）。
- 行业普涨但蓝筹滞涨本身即构成 Buffett 视角的重要信号，可直接用于风险评估。

## 输出纪律

- 研报正文不得暴露 curl、浏览器、编码转换等工程细节。
- 缺失数据来源需在对应章节标注，或在 evidence `_meta.source_events` 中记录。
- 结尾必须包含标准免责声明。
