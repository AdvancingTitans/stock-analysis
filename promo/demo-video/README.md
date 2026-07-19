# stock-analysis demo video

Editable bilingual 72-second, 1920×1080 Remotion product demo.

```bash
npm install
npm run studio
npm run still
npm run render
```

- Compositions: `StockAnalysisDemo` (English), `StockAnalysisDemoZh` (简体中文)
- Frame rate: 30 fps
- Final outputs:
  - `out/stock-analysis-demo-en.mp4`
  - `out/stock-analysis-demo-zh-CN.mp4`
- Preview stills: `out/preview-en.png`, `out/preview-zh-CN.png`

The demo intentionally uses no voiceover or music, so it works in muted social feeds and can be localized by editing the scene copy in `src/video.jsx`.

The current cut follows the company-research reasoning chain: premise audit → comparable evidence → forward product-line/SOTP model → market-implied earnings → expectation-gap reconciliation → monitoring triggers and committee review.
