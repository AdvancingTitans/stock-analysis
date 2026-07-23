# Assets

Screenshots and share cards used by the README and [report directory](../reports/).

## Screenshot Sets

| Set | Files |
|---|---|
| Global market recap | `全球市场复盘_1.png` to `全球市场复盘_3.png` |
| Global recap, Buffett lens | `全球市场复盘（巴菲特）_1.png` to `全球市场复盘（巴菲特）_3.png` |
| Global recap, Simons lens | `全球市场西蒙斯视角行情分析_1.png` to `全球市场西蒙斯视角行情分析_5.png` |
| Moutai, Buffett lens | `贵州茅台个股分析（巴菲特）_1.png` to `贵州茅台个股分析（巴菲特）_4.png` |
| Moutai, Simons lens | `贵州茅台个股分析（西蒙斯）_1.png` to `贵州茅台个股分析（西蒙斯）_4.png` |
| Semiconductor fund profile | `半导体基金分析_1.png` to `半导体基金分析_3.png` |

## Share Cards

- `social-preview.png`: GitHub repository social preview.
- `share-cn-1.png`: Chinese social-share card.
- `share-x-1.png`, `share-x-2.png`: short-form X/Twitter share cards.

## Product Architecture and Demo

- `investor-research-architecture-en.gif`: English investor-to-report architecture animation.
- `investor-research-architecture-zh-CN.gif`: Simplified Chinese architecture animation.
- `diagrams/investor-research-architecture-*.source.json`: semantic inputs for the English and Simplified Chinese architecture diagrams.
- `diagrams/investor-research-architecture-*.svg`: validated semantic SVG sources used to render the GIFs.
- `diagrams/investor-research-architecture-*.layout.json`: geometry and layout validation reports.
- `diagrams/investor-research-architecture-*.motion.json`: GIF motion-contract validation reports.
- `demo-video-preview-en.png`: English poster linking to the 72-second Remotion demo.
- `demo-video-preview-zh-CN.png`: Simplified Chinese poster linking to the 72-second Remotion demo.

The architecture animations use the `fireworks-tech-graph` `agent` template and
the `agent-orchestration` motion contract. To reproduce one locale, replace the
placeholders below with the installed skill path and the desired locale (`en` or
`zh-CN`):

```bash
python3 <fireworks-skill-root>/scripts/generate-from-template.py agent \
  assets/diagrams/investor-research-architecture-<locale>.svg \
  "$(jq -c . assets/diagrams/investor-research-architecture-<locale>.source.json)" \
  --layout-report assets/diagrams/investor-research-architecture-<locale>.layout.json

python3 <fireworks-skill-root>/scripts/fireworks.py animate \
  assets/diagrams/investor-research-architecture-<locale>.svg \
  assets/investor-research-architecture-<locale>.gif \
  --preset agent-orchestration --duration 5.75 --fps 20 --width 960 \
  --report assets/diagrams/investor-research-architecture-<locale>.motion.json
```

The generator and animator require Python 3, Node.js 18+, Chrome/Chromium,
FFmpeg/FFprobe, `jq`, and the runtime dependencies bundled with the skill.
