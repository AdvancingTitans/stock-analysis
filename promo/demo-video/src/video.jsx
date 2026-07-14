import React from 'react';
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
const fontFamily = 'Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

const C = {
  ink: '#E9F0EA',
  muted: '#99A79D',
  bg: '#07100D',
  panel: '#0C1713',
  line: '#26372F',
  green: '#65E6A5',
  lime: '#C5F476',
  amber: '#F3C677',
  red: '#FF817A',
};

const fade = (frame, duration) =>
  interpolate(frame, [0, 14, duration - 14, duration], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

const rise = (frame, fps, delay = 0) => {
  const p = spring({frame: frame - delay, fps, config: {damping: 20, stiffness: 110}});
  return {opacity: p, transform: `translateY(${32 * (1 - p)}px)`};
};

const Grid = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        backgroundColor: C.bg,
        backgroundImage:
          'linear-gradient(rgba(101,230,165,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(101,230,165,.035) 1px, transparent 1px)',
        backgroundSize: '64px 64px',
        backgroundPosition: `${frame * 0.12}px ${frame * 0.06}px`,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(circle at 72% 35%, rgba(31,112,78,.18), transparent 33%), radial-gradient(circle at 18% 80%, rgba(197,244,118,.08), transparent 28%)',
        }}
      />
    </AbsoluteFill>
  );
};

const Shell = ({children, label = 'stock-analysis / demo', zh}) => (
  <AbsoluteFill style={{fontFamily, color: C.ink}}>
    <Grid />
    <div
      style={{
        position: 'absolute',
        top: 46,
        left: 70,
        right: 70,
        display: 'flex',
        justifyContent: 'space-between',
        color: C.muted,
        fontSize: 17,
        letterSpacing: 1.7,
        textTransform: 'uppercase',
      }}
    >
      <span>{label}</span>
      <span>{zh ? '证据优先 · 开源 · MIT' : 'evidence-first · open source · MIT'}</span>
    </div>
    {children}
  </AbsoluteFill>
);

const Badge = ({children, tone = C.green}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      border: `1px solid ${tone}66`,
      color: tone,
      borderRadius: 999,
      padding: '9px 16px',
      fontSize: 18,
      fontWeight: 600,
      letterSpacing: 0.3,
    }}
  >
    {children}
  </span>
);

const Scene = ({duration, children, label, zh}) => {
  const frame = useCurrentFrame();
  return (
    <Shell label={label} zh={zh}>
      <AbsoluteFill style={{opacity: fade(frame, duration)}}>{children}</AbsoluteFill>
    </Shell>
  );
};

const Hook = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene duration={210} label={zh ? '问题' : 'the problem'} zh={zh}>
      <div style={{position: 'absolute', left: 150, top: 205, width: 1460}}>
        <div style={rise(frame, fps)}>
          <Badge tone={C.amber}>{zh ? '当下的市场 AI' : 'MARKET AI, TODAY'}</Badge>
        </div>
        <div style={{...rise(frame, fps, 10), marginTop: 38, fontSize: 80, lineHeight: 1.08, fontWeight: 600}}>
          {zh ? '输入一个提示词。' : 'A prompt goes in.'}
          <br />
          <span style={{color: C.amber}}>{zh ? '输出一段自信满满的结论。' : 'A confident paragraph comes out.'}</span>
        </div>
        <div style={{...rise(frame, fps, 45), marginTop: 40, fontSize: 30, color: C.muted}}>
          {zh ? '但你能检查每条观点背后的证据吗？' : 'But can you inspect the evidence behind every claim?'}
        </div>
      </div>
    </Scene>
  );
};

const Gap = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = zh
    ? [['来源时间戳', '未知'], ['缺失字段', '静默补全'], ['失败的数据路由', '隐藏'], ['Agent 交接', '只有文本']]
    : [['Source timestamp', 'unknown'], ['Missing fields', 'silently filled'], ['Failed data route', 'hidden'], ['Agent handoff', 'prose only']];
  return (
    <Scene duration={180} label={zh ? '可信缺口' : 'the trust gap'} zh={zh}>
      <div style={{position: 'absolute', left: 150, right: 150, top: 170}}>
        <div style={{fontSize: 54, fontWeight: 600, ...rise(frame, fps)}}>{zh ? '流畅，不等于可审计。' : 'Fluent is not the same as auditable.'}</div>
        <div style={{marginTop: 45, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
          {items.map(([a, b], i) => (
            <div
              key={a}
              style={{
                ...rise(frame, fps, 12 + i * 8),
                display: 'flex',
                justifyContent: 'space-between',
                padding: '28px 30px',
                border: `1px solid ${C.line}`,
                borderRadius: 16,
                background: `${C.panel}E6`,
                fontSize: 25,
              }}
            >
              <span>{a}</span>
              <span style={{color: C.red}}>{b}</span>
            </div>
          ))}
        </div>
      </div>
    </Scene>
  );
};

const Brand = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame, fps, config: {damping: 18, stiffness: 75}});
  return (
    <Scene duration={210} label={zh ? '另一种选择' : 'the alternative'} zh={zh}>
      <div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center'}}>
        <div style={{textAlign: 'center', transform: `scale(${0.92 + p * 0.08})`, opacity: p}}>
          <div style={{fontSize: 26, color: C.muted, letterSpacing: 6, marginBottom: 28}}>{zh ? '开源市场研究' : 'OPEN-SOURCE MARKET RESEARCH'}</div>
          <div style={{fontSize: 104, fontWeight: 700, letterSpacing: -4}}>
            stock<span style={{color: C.green}}>-analysis</span>
          </div>
          <div style={{fontSize: 39, marginTop: 25}}>{zh ? '从证据开始，以可审计的报告结束。' : 'Starts with evidence. Ends with a report you can audit.'}</div>
          <div style={{marginTop: 46, display: 'flex', justifyContent: 'center', gap: 14}}>
            <Badge>{zh ? 'A 股 · 港股 · 美股' : 'A · HK · US'}</Badge>
            <Badge>{zh ? '基金' : 'Funds'}</Badge>
            <Badge>{zh ? '投资组合' : 'Portfolios'}</Badge>
            <Badge tone={C.lime}>{zh ? 'Agent 就绪 JSON' : 'Agent-ready JSON'}</Badge>
          </div>
        </div>
      </div>
    </Scene>
  );
};

const Terminal = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const command = 'stock-analysis --market stock-review --symbol 600519 --emit-evidence';
  const chars = Math.floor(interpolate(frame, [34, 124], [0, command.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const rows = zh
    ? [['代码标准化', '600519 → 1.600519 · 上交所'], ['来源路由', '已验证的公开数据源降级'], ['数据校验', '交易日 · 币种 · 报告期'], ['写入文件', 'report.md + company_evidence_600519.json']]
    : [['normalize', '600519 → 1.600519 · SSE'], ['route', 'validated public-source fallback'], ['validate', 'trade date · currency · period'], ['write', 'report.md + company_evidence_600519.json']];
  return (
    <Scene duration={360} label={zh ? '一个确定性命令' : 'one deterministic command'} zh={zh}>
      <div style={{position: 'absolute', left: 135, right: 135, top: 148}}>
        <div style={{fontSize: 48, fontWeight: 600, ...rise(frame, fps)}}>{zh ? '提出研究问题，保留证据链。' : 'Ask a research question. Keep the trail.'}</div>
        <div
          style={{
            ...rise(frame, fps, 8),
            marginTop: 36,
            borderRadius: 18,
            border: `1px solid ${C.line}`,
            background: '#07100DEC',
            boxShadow: '0 30px 80px rgba(0,0,0,.38)',
            overflow: 'hidden',
          }}
        >
          <div style={{height: 52, display: 'flex', alignItems: 'center', gap: 10, padding: '0 20px', background: '#111E19'}}>
            {[C.red, C.amber, C.green].map((x) => <span key={x} style={{width: 12, height: 12, borderRadius: 99, background: x}} />)}
            <span style={{marginLeft: 12, color: C.muted, fontSize: 16}}>research-terminal</span>
          </div>
          <div style={{padding: '34px 38px 38px', fontFamily: 'SFMono-Regular, Menlo, monospace', fontSize: 23, lineHeight: 1.75}}>
            <div><span style={{color: C.green}}>$</span> {command.slice(0, chars)}<span style={{opacity: frame % 18 < 9 ? 1 : 0}}>▋</span></div>
            <div style={{height: 28}} />
            {rows.map(([k, v], i) => {
              const show = spring({frame: frame - 140 - i * 28, fps, config: {damping: 18}});
              return (
                <div key={k} style={{opacity: show, transform: `translateY(${10 * (1 - show)}px)`}}>
                  <span style={{color: C.lime, display: 'inline-block', minWidth: zh ? 170 : 185}}>✓ {zh ? k : k.padEnd(10)}</span>
                  <span style={{color: C.muted}}>{v}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Scene>
  );
};

const Evidence = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const modules = zh
    ? [['C1', '商业质量', '已验证', 'VERIFIED'], ['C2', '财务质量', '已验证', 'VERIFIED'], ['C3', '增长质量', '已验证', 'VERIFIED'], ['C4', '护城河', '缺口', 'GAP'], ['C5', '资本配置', '部分', 'PARTIAL'], ['C6', '估值', '已验证', 'VERIFIED'], ['C7', '风险', '已验证', 'VERIFIED'], ['C8', '催化剂', '部分', 'PARTIAL']]
    : [['C1', 'Business', 'VERIFIED', 'VERIFIED'], ['C2', 'Financials', 'VERIFIED', 'VERIFIED'], ['C3', 'Growth', 'VERIFIED', 'VERIFIED'], ['C4', 'Moat', 'GAP', 'GAP'], ['C5', 'Allocation', 'PARTIAL', 'PARTIAL'], ['C6', 'Valuation', 'VERIFIED', 'VERIFIED'], ['C7', 'Risk', 'VERIFIED', 'VERIFIED'], ['C8', 'Catalysts', 'PARTIAL', 'PARTIAL']];
  return (
    <Scene duration={330} label={zh ? '公司证据包 · C1–C8' : 'company evidence pack · C1–C8'} zh={zh}>
      <div style={{position: 'absolute', left: 130, right: 130, top: 140}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'end'}}>
          <div>
            <Badge>{zh ? '已验证事实' : 'VERIFIED FACTS'}</Badge>
            <div style={{fontSize: 55, fontWeight: 600, marginTop: 25}}>{zh ? '证据是结构化的。' : 'Evidence has structure.'}</div>
          </div>
          <div style={{textAlign: 'right'}}>
            <div style={{fontSize: 20, color: C.muted}}>{zh ? '每条事实都带有' : 'every fact carries'}</div>
            <div style={{fontSize: 25, fontWeight: 600, color: C.green, marginTop: 12}}>{zh ? '来源 · 期间 · 置信度' : 'source · period · confidence'}</div>
          </div>
        </div>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginTop: 40}}>
          {modules.map(([id, name, status, statusKey], i) => {
            const p = spring({frame: frame - 10 - i * 7, fps, config: {damping: 19}});
            const tone = statusKey === 'GAP' ? C.amber : statusKey === 'PARTIAL' ? C.lime : C.green;
            return (
              <div key={id} style={{opacity: p, padding: 24, borderRadius: 16, background: C.panel, border: `1px solid ${C.line}`}}>
                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 20}}>
                  <span style={{color: C.green, fontWeight: 700}}>{id}</span><span style={{color: tone, fontSize: 15, letterSpacing: 1}}>{status}</span>
                </div>
                <div style={{fontSize: 24, marginTop: 18}}>{name}</div>
                <div style={{height: 5, background: '#1A2923', borderRadius: 99, marginTop: 22}}>
                  <div style={{width: `${p * 100}%`, height: '100%', borderRadius: 99, background: tone}} />
                </div>
              </div>
            );
          })}
        </div>
        <div style={{marginTop: 25, color: C.amber, fontSize: 22}}>{zh ? '△ 缺失的护城河证据保持缺失——不猜测，也不用零值代替。' : '△ Missing moat evidence stays missing — never guessed, never replaced with zero.'}</div>
      </div>
    </Scene>
  );
};

const OutputCard = ({title, eyebrow, children, delay, frame, fps}) => (
  <div
    style={{
      ...rise(frame, fps, delay),
      width: 735,
      height: 590,
      borderRadius: 18,
      border: `1px solid ${C.line}`,
      background: C.panel,
      padding: 34,
      boxSizing: 'border-box',
      boxShadow: '0 24px 70px rgba(0,0,0,.25)',
    }}
  >
    <div style={{fontSize: 16, color: C.green, letterSpacing: 2}}>{eyebrow}</div>
    <div style={{fontSize: 33, fontWeight: 600, marginTop: 11}}>{title}</div>
    <div style={{marginTop: 28}}>{children}</div>
  </div>
);

const Outputs = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene duration={300} label={zh ? '双输出 · 单一事实来源' : 'two outputs · one source of truth'} zh={zh}>
      <div style={{position: 'absolute', left: 145, right: 145, top: 142}}>
        <div style={{fontSize: 50, fontWeight: 600}}>{zh ? '人能读，Agent 能复用。' : 'Readable by humans. Reusable by agents.'}</div>
        <div style={{display: 'flex', gap: 24, marginTop: 38}}>
          <OutputCard title={zh ? '研究报告' : 'Research report'} eyebrow="MARKDOWN" delay={6} frame={frame} fps={fps}>
            {(zh ? ['# 贵州茅台 · 600519', '## 已核验事实', '营收 / 利润率 / ROE 及对应期间', '## 反向证据', '## 缺失证据与后续检查'] : ['# Kweichow Moutai · 600519', '## Checked facts', 'Revenue / margin / ROE with periods', '## Counter-evidence', '## Missing evidence & next checks']).map((x, i) => (
              <div key={x} style={{fontSize: 20 + (i === 0 ? 4 : 0), color: i === 0 ? C.ink : C.muted, marginBottom: 23, borderBottom: i === 0 ? `1px solid ${C.line}` : 'none', paddingBottom: i === 0 ? 20 : 0}}>{x}</div>
            ))}
          </OutputCard>
          <OutputCard title={zh ? '证据包' : 'Evidence Pack'} eyebrow="JSON" delay={14} frame={frame} fps={fps}>
            <pre style={{margin: 0, color: C.muted, fontSize: 18, lineHeight: 1.62, fontFamily: 'SFMono-Regular, Menlo, monospace'}}>
              <span style={{color: C.ink}}>{'{'}</span>{'\n'}
              {'  '}<span style={{color: C.lime}}>&quot;symbol&quot;</span>: <span style={{color: C.amber}}>&quot;600519&quot;</span>,{`\n`}
              {'  '}<span style={{color: C.lime}}>&quot;trade_date&quot;</span>: <span style={{color: C.amber}}>&quot;2026-07-14&quot;</span>,{`\n`}
              {'  '}<span style={{color: C.lime}}>&quot;source&quot;</span>: <span style={{color: C.amber}}>&quot;public_market_data&quot;</span>,{`\n`}
              {'  '}<span style={{color: C.lime}}>&quot;confidence&quot;</span>: <span style={{color: C.green}}>0.91</span>,{`\n`}
              {'  '}<span style={{color: C.lime}}>&quot;gaps&quot;</span>: [{`\n`}
              {'    '}<span style={{color: C.amber}}>&quot;{zh ? '护城河证据不可用' : 'moat evidence unavailable'}&quot;</span>{`\n`}
              {'  '}] {`\n`}
              <span style={{color: C.ink}}>{'}'}</span>
            </pre>
          </OutputCard>
        </div>
      </div>
    </Scene>
  );
};

const AgentFlow = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nodes = zh
    ? [['01', '投资问题', '“审查 600519”'], ['02', 'stock-analysis', '获取 · 标准化 · 校验'], ['03', '证据包', '事实 · 来源 · 缺口'], ['04', '你的 Agent', '总结，但不编造']]
    : [['01', 'Investor question', '“Review 600519”'], ['02', 'stock-analysis', 'fetch · normalize · validate'], ['03', 'Evidence Pack', 'facts · sources · gaps'], ['04', 'Your Agent', 'summarize without inventing']];
  return (
    <Scene duration={300} label={zh ? 'Agent 原生工作流' : 'agent-native workflow'} zh={zh}>
      <div style={{position: 'absolute', left: 120, right: 120, top: 175}}>
        <div style={{fontSize: 52, fontWeight: 600, textAlign: 'center'}}>{zh ? '给 Agent 证据，而不是允许它即兴发挥。' : 'Give your Agent evidence, not permission to improvise.'}</div>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 80}}>
          {nodes.map(([id, title, sub], i) => {
            const p = spring({frame: frame - i * 14, fps, config: {damping: 18}});
            return (
              <React.Fragment key={id}>
                <div style={{opacity: p, transform: `scale(${0.9 + p * 0.1})`, width: 340, height: 220, padding: 27, boxSizing: 'border-box', borderRadius: 18, border: `1px solid ${i === 2 ? C.green : C.line}`, background: C.panel}}>
                  <div style={{fontSize: 17, color: C.green, letterSpacing: 2}}>{id}</div>
                  <div style={{fontSize: 27, fontWeight: 600, marginTop: 28}}>{title}</div>
                  <div style={{fontSize: 18, color: C.muted, lineHeight: 1.45, marginTop: 15}}>{sub}</div>
                </div>
                {i < nodes.length - 1 && <div style={{width: 58, height: 1, background: C.green, opacity: p}} />}
              </React.Fragment>
            );
          })}
        </div>
        <div style={{display: 'flex', justifyContent: 'center', gap: 16, marginTop: 58}}>
          <Badge>Codex</Badge><Badge>Claude Code</Badge><Badge>Hermes</Badge><Badge>GitHub Actions</Badge>
        </div>
      </div>
    </Scene>
  );
};

const Close = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene duration={270} label={zh ? '开源 · MIT' : 'open source · MIT'} zh={zh}>
      <div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center'}}>
        <div style={{textAlign: 'center', width: 1500}}>
          <div style={{...rise(frame, fps), fontSize: 78, lineHeight: 1.06, fontWeight: 650}}>
            {zh ? '让你的 Agent 在市场研究中' : 'Market research your Agent'}<br />
            {zh ? <><span style={{color: C.green}}>展示完整证据链</span>。</> : <>can <span style={{color: C.green}}>show its work</span> for.</>}
          </div>
          <div style={{...rise(frame, fps, 14), display: 'inline-flex', marginTop: 56, padding: '24px 34px', border: `1px solid ${C.line}`, borderRadius: 14, background: C.panel, fontFamily: 'SFMono-Regular, Menlo, monospace', fontSize: 27}}>
            <span style={{color: C.green, marginRight: 17}}>$</span> uv tool install stock-analysis
          </div>
          <div style={{...rise(frame, fps, 24), marginTop: 42, fontSize: 28, color: C.muted}}>github.com/AdvancingTitans/stock-analysis</div>
          <div style={{...rise(frame, fps, 34), marginTop: 28, display: 'flex', justifyContent: 'center', gap: 12}}>
            <Badge>{zh ? 'A 股 / 港股 / 美股' : 'A / HK / US'}</Badge><Badge>Markdown + JSON</Badge><Badge tone={C.lime}>{zh ? '无需 LLM' : 'No LLM required'}</Badge>
          </div>
        </div>
      </div>
    </Scene>
  );
};

export const StockAnalysisDemo = ({language = 'en'}) => {
  const zh = language === 'zh';
  return (
  <AbsoluteFill style={{background: C.bg}}>
    <Sequence from={0} durationInFrames={210}><Hook zh={zh} /></Sequence>
    <Sequence from={210} durationInFrames={180}><Gap zh={zh} /></Sequence>
    <Sequence from={390} durationInFrames={210}><Brand zh={zh} /></Sequence>
    <Sequence from={600} durationInFrames={360}><Terminal zh={zh} /></Sequence>
    <Sequence from={960} durationInFrames={330}><Evidence zh={zh} /></Sequence>
    <Sequence from={1290} durationInFrames={300}><Outputs zh={zh} /></Sequence>
    <Sequence from={1590} durationInFrames={300}><AgentFlow zh={zh} /></Sequence>
    <Sequence from={1890} durationInFrames={270}><Close zh={zh} /></Sequence>
  </AbsoluteFill>
  );
};
