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
    <Scene duration={210} label={zh ? '从投资问题开始' : 'start with the investor question'} zh={zh}>
      <div style={{position: 'absolute', left: 150, top: 205, width: 1460}}>
        <div style={rise(frame, fps)}>
          <Badge tone={C.amber}>{zh ? '正向建模 + 逆向验价' : 'FORWARD MODEL + REVERSE PRICE'}</Badge>
        </div>
        <div style={{...rise(frame, fps, 10), marginTop: 38, fontSize: 80, lineHeight: 1.08, fontWeight: 600}}>
          {zh ? '不只预测利润' : 'Do more than forecast earnings'}
          <br />
          <span style={{color: C.amber}}>{zh ? '还要解释股价' : 'explain what the price assumes'}</span>
        </div>
        <div style={{...rise(frame, fps, 45), marginTop: 40, fontSize: 30, color: C.muted}}>
          {zh ? '把真正的投资分歧翻译成可验证指标' : 'Translate the real disagreement into testable operating metrics'}
        </div>
      </div>
    </Scene>
  );
};

const Gap = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = zh
    ? [['前提可能有误', '先核口径 再解释'], ['证据相互冲突', '同口径后再仲裁'], ['正向模型很好看', '市值可能早已计价'], ['下一季看什么', '指标 日期与观点变化']]
    : [['The premise may be wrong', 'verify scope before explaining'], ['Evidence can conflict', 'compare like with like'], ['The model can look great', 'the price may already discount it'], ['What changes next quarter?', 'metric date and view trigger']];
  return (
    <Scene duration={180} label={zh ? '不止今天大盘' : 'more than a daily index recap'} zh={zh}>
      <div style={{position: 'absolute', left: 150, right: 150, top: 170}}>
        <div style={{fontSize: 54, fontWeight: 600, ...rise(frame, fps)}}>{zh ? '成熟研究先处理四个难题' : 'Disciplined research solves four hard problems first'}</div>
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
              <span style={{color: C.green}}>{b}</span>
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
    <Scene duration={210} label={zh ? '对象 问题与视角' : 'asset question and lens'} zh={zh}>
      <div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center'}}>
        <div style={{textAlign: 'center', transform: `scale(${0.92 + p * 0.08})`, opacity: p}}>
          <div style={{fontSize: 26, color: C.muted, letterSpacing: 6, marginBottom: 28}}>{zh ? '一句话指定对象 问题与视角' : 'NAME THE ASSET QUESTION AND LENS'}</div>
          <div style={{fontSize: 104, fontWeight: 700, letterSpacing: -4}}>
            stock<span style={{color: C.green}}>-analysis</span>
          </div>
          <div style={{fontSize: 39, marginTop: 25}}>{zh ? '核验事实 建模经营 再解释市场定价' : 'Verify facts. Model the business. Explain the price.'}</div>
          <div style={{marginTop: 46, display: 'flex', justifyContent: 'center', gap: 14}}>
            <Badge>{zh ? '全球行情' : 'Global markets'}</Badge>
            <Badge>{zh ? '个股' : 'Stocks'}</Badge>
            <Badge>{zh ? '基金' : 'Funds'}</Badge>
            <Badge tone={C.lime}>{zh ? '15种投资框架' : '15 investment frameworks'}</Badge>
          </div>
        </div>
      </div>
    </Scene>
  );
};

const Terminal = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const command = 'scripts/install-agent-entrypoints.sh codex';
  const chars = Math.floor(interpolate(frame, [22, 82], [0, command.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const prompts = zh
    ? [
        '复盘A股盘前 区分尚未开始 集合竞价与盘中证据',
        '分析腾讯和苹果 优先核验HKEX SEC与公司IR原文',
        '比较日韩持仓量价 组合相关性与逐日汇率归因',
      ]
    : [
        'Recap A-share premarket and separate not-yet-open auction and intraday evidence',
        'Research Tencent and Apple with HKEX SEC and issuer originals first',
        'Compare JP/KR holdings liquidity portfolio correlation and daily FX attribution',
      ];
  return (
    <Scene duration={360} label={zh ? '安装 Skill 后直接提问' : 'install the Skill then ask'} zh={zh}>
      <div style={{position: 'absolute', left: 135, right: 135, top: 125}}>
        <div style={{fontSize: 48, fontWeight: 600, ...rise(frame, fps)}}>{zh ? '安装 Skill 直接问你的投资问题' : 'Install the Skill then ask your investment question'}</div>
        <div
          style={{
            ...rise(frame, fps, 8),
            marginTop: 30,
            borderRadius: 18,
            border: `1px solid ${C.line}`,
            background: '#07100DEC',
            boxShadow: '0 30px 80px rgba(0,0,0,.38)',
            overflow: 'hidden',
          }}
        >
          <div style={{height: 52, display: 'flex', alignItems: 'center', gap: 10, padding: '0 20px', background: '#111E19'}}>
            {[C.red, C.amber, C.green].map((x) => <span key={x} style={{width: 12, height: 12, borderRadius: 99, background: x}} />)}
            <span style={{marginLeft: 12, color: C.muted, fontSize: 16}}>skill-installer</span>
          </div>
          <div style={{padding: '25px 38px 26px', fontFamily: 'SFMono-Regular, Menlo, monospace', fontSize: 22, lineHeight: 1.65}}>
            <div><span style={{color: C.green}}>$</span> uv tool install stock-analysis</div>
            <div><span style={{color: C.green}}>$</span> {command.slice(0, chars)}<span style={{opacity: frame % 18 < 9 ? 1 : 0}}>▋</span></div>
            <div style={{...rise(frame, fps, 92), color: C.lime, marginTop: 12}}>✓ {zh ? '已安装 全球市场 · 公司研究 · 一手证据补齐' : 'installed global markets · company research · primary-evidence reach'}</div>
          </div>
        </div>
        <div style={{...rise(frame, fps, 122), marginTop: 20, border: `1px solid ${C.line}`, borderRadius: 18, background: C.panel, padding: '20px 28px'}}>
          <div style={{fontSize: 16, color: C.green, letterSpacing: 2}}>{zh ? '向 AGENT 提问' : 'ASK YOUR AGENT'}</div>
          <div style={{display: 'grid', gap: 9, marginTop: 13}}>
            {prompts.map((prompt, i) => (
              <div key={prompt} style={{...rise(frame, fps, 145 + i * 22), fontSize: 20, color: i === 0 ? C.ink : C.muted}}>
                <span style={{color: C.green, marginRight: 12}}>0{i + 1}</span>{prompt}
              </div>
            ))}
          </div>
          <div style={{...rise(frame, fps, 220), marginTop: 14, color: C.lime, fontSize: 18}}>
            {zh ? '识别对象 问题与视角 调用对应证据流程' : 'The Agent maps asset question and lens to the matching evidence workflow'}
          </div>
        </div>
      </div>
    </Scene>
  );
};

const Evidence = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const coverage = zh ? ['A股', '港股', '美股', '日股', '韩股', '基金/组合'] : ['A-shares', 'Hong Kong', 'US stocks', 'Japan', 'Korea', 'Funds/portfolios'];
  const evidenceTypes = zh
    ? ['交易时段与日历', '多源量价', 'SEC与年报一手财务', 'Agent一手证据补齐', '本币成交额与60日波动', '组合相关性与汇率归因', '正逆向估值', '动态投委会']
    : ['Sessions and calendars', 'Multi-source price/volume', 'SEC and annual reports', 'Agent primary-evidence reach', 'Local ADV and 60d volatility', 'Correlation and FX attribution', 'Forward/reverse valuation', 'Dynamic committee'];
  return (
    <Scene duration={330} label={zh ? '数据广度与证据深度' : 'market breadth and evidence depth'} zh={zh}>
      <div style={{position: 'absolute', left: 130, right: 130, top: 115}}>
        <Badge>{zh ? '多市场 多类型 多来源' : 'MULTI-MARKET · MULTI-SOURCE'}</Badge>
        <div style={{fontSize: 54, fontWeight: 600, marginTop: 22}}>{zh ? '不把假设写成事实 不把市值留在模型之外' : 'Keep assumptions separate—and price inside the model'}</div>
        <div style={{marginTop: 30, padding: 24, borderRadius: 18, border: `1px solid ${C.line}`, background: C.panel}}>
          <div style={{fontSize: 16, color: C.green, letterSpacing: 2}}>{zh ? '覆盖范围' : 'COVERAGE'}</div>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 11, marginTop: 17}}>
            {coverage.map((item, i) => <Badge key={item} tone={i === 4 ? C.lime : C.green}>{item}</Badge>)}
          </div>
        </div>
        <div style={{marginTop: 16, padding: 24, borderRadius: 18, border: `1px solid ${C.line}`, background: C.panel}}>
          <div style={{fontSize: 16, color: C.green, letterSpacing: 2}}>{zh ? '证据类型' : 'EVIDENCE TYPES'}</div>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 11, marginTop: 17}}>
            {evidenceTypes.map((item, i) => (
              <span key={item} style={{...rise(frame, fps, 8 + i * 4), padding: '9px 14px', borderRadius: 9, background: '#14231D', color: C.ink, fontSize: 18}}>{item}</span>
            ))}
          </div>
        </div>
        <div style={{marginTop: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: C.muted, fontSize: 19}}>
          <span style={{color: C.amber}}>{zh ? '多源自动切换 缺失项明确保留' : 'Multi-source routing · Explicit gaps'}</span>
        </div>
      </div>
    </Scene>
  );
};

const Outputs = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const groups = zh
    ? [
        ['长期经营', ['巴菲特', '芒格', '段永平', '张坤']],
        ['价值逆向', ['格雷厄姆', '卡拉曼', '冯柳']],
        ['成长创新', ['彼得·林奇', '欧奈尔', '伍德']],
        ['趋势量化', ['利弗莫尔', '米勒维尼', '西蒙斯']],
        ['宏观动态', ['达利欧', '索罗斯']],
      ]
    : [
        ['Long-term business', ['Buffett', 'Munger', 'Duan Yongping', 'Zhang Kun']],
        ['Value and contrarian', ['Graham', 'Klarman', 'Feng Liu']],
        ['Growth and innovation', ['Peter Lynch', "O’Neil", 'Wood']],
        ['Trend and quant', ['Livermore', 'Minervini', 'Simons']],
        ['Macro and reflexivity', ['Dalio', 'Soros']],
      ];
  return (
    <Scene duration={300} label={zh ? '15种投资框架' : '15 investment frameworks'} zh={zh}>
      <div style={{position: 'absolute', left: 105, right: 105, top: 115}}>
        <div style={{fontSize: 52, fontWeight: 600}}>{zh ? '同一批结构化指标 15种投资框架' : 'One structured evidence base. 15 investment frameworks.'}</div>
        <div style={{fontSize: 24, color: C.muted, marginTop: 14}}>{zh ? '从商业质量到量价趋势 从宏观周期到统计检验' : 'Business quality to price action · Macro regimes to statistical validation'}</div>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginTop: 35}}>
          {groups.map(([title, names], i) => (
            <div key={title} style={{...rise(frame, fps, 6 + i * 7), minHeight: 330, padding: 25, borderRadius: 18, border: `1px solid ${i === 3 ? C.green : C.line}`, background: C.panel}}>
              <div style={{fontSize: 17, color: i === 3 ? C.lime : C.green, letterSpacing: 1.4}}>{title}</div>
              <div style={{marginTop: 24, display: 'grid', gap: 17}}>
                {names.map((name) => <div key={name} style={{fontSize: 23, fontWeight: 600}}>{name}</div>)}
              </div>
            </div>
          ))}
        </div>
        <div style={{marginTop: 26, display: 'flex', gap: 16}}>
          <Badge>{zh ? '单框架深挖' : 'Single-framework depth'}</Badge>
          <Badge>{zh ? '根据问题动态选择6位' : 'Six selected for each question'}</Badge>
          <Badge tone={C.lime}>{zh ? '双框架对照' : 'Two-framework comparison'}</Badge>
        </div>
      </div>
    </Scene>
  );
};

const AgentFlow = ({zh}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const flows = zh
    ? [
        ['识别市场与时段', '交易日历和可用性状态', '尚未产生不等于数据源故障'],
        ['取得结构化证据', '行情 财务 流动性 汇率', '日期口径与来源可审计'],
        ['补发行人原文', '公司IR 交易所 监管机构', '缺失仍保留 不用摘要冒充'],
        ['形成判断', '正逆向估值与投委会', '反证 条件与持续跟踪'],
      ]
    : [
        ['Resolve market and session', 'calendar and availability state', 'not-yet-created is not source failure'],
        ['Gather structured evidence', 'quotes financials liquidity and FX', 'auditable date scope and source'],
        ['Reach issuer originals', 'IR exchange and regulator', 'keep gaps when originals are absent'],
        ['Form the view', 'forward/reverse valuation and committee', 'counter-evidence conditions and tracking'],
      ];
  return (
    <Scene duration={300} label={zh ? '从问题到对应报告' : 'from question to the matching report'} zh={zh}>
      <div style={{position: 'absolute', left: 120, right: 120, top: 125}}>
        <div style={{fontSize: 52, fontWeight: 600}}>{zh ? '从全球证据 到可持续验证的判断' : 'From global evidence to a continuously testable view'}</div>
        <div style={{display: 'grid', gap: 14, marginTop: 38}}>
          {flows.map(([question, evidence, report], i) => {
            const p = spring({frame: frame - i * 18, fps, config: {damping: 18}});
            return (
              <div key={question} style={{opacity: p, transform: `translateY(${16 * (1 - p)}px)`, display: 'grid', gridTemplateColumns: '1fr 1.1fr 1.25fr', alignItems: 'center', gap: 18}}>
                {[question, evidence, report].map((textValue, j) => (
                  <div key={textValue} style={{minHeight: 128, padding: '24px 26px', boxSizing: 'border-box', borderRadius: 16, border: `1px solid ${j === 1 ? C.green : C.line}`, background: C.panel}}>
                    <div style={{fontSize: 14, color: j === 1 ? C.lime : C.green, letterSpacing: 1.5}}>{j === 0 ? (zh ? '研究阶段' : 'STAGE') : j === 1 ? (zh ? '确定性计算' : 'DETERMINISTIC STEP') : (zh ? '研究输出' : 'RESEARCH OUTPUT')}</div>
                    <div style={{fontSize: 21, lineHeight: 1.4, marginTop: 14}}>{textValue}</div>
                  </div>
                ))}
              </div>
            );
          })}
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
          <div style={{...rise(frame, fps), fontSize: zh ? 64 : 56, lineHeight: 1.15, fontWeight: 650}}>
            {zh ? '正向回答 公司能赚多少' : 'Forward: what can the business earn?'}<br />
            {zh ? '逆向回答 股价已经相信多少' : 'Reverse: what does the price already believe?'}<br />
            <span style={{color: C.green}}>{zh ? '真正的机会 藏在两者之间' : 'The investable question lives in the gap.'}</span>
          </div>
          <div style={{...rise(frame, fps, 14), display: 'inline-flex', marginTop: 42, padding: '21px 30px', border: `1px solid ${C.line}`, borderRadius: 14, background: C.panel, fontFamily: 'SFMono-Regular, Menlo, monospace', fontSize: 25}}>
            <span style={{color: C.green, marginRight: 17}}>$</span> scripts/install-agent-entrypoints.sh codex
          </div>
          <div style={{...rise(frame, fps, 24), marginTop: 30, fontSize: 26, color: C.muted}}>github.com/AdvancingTitans/stock-analysis</div>
          <div style={{...rise(frame, fps, 34), marginTop: 24, display: 'flex', justifyContent: 'center', gap: 12}}>
            <Badge>{zh ? 'A/HK/US/JP/KR' : 'A/HK/US/JP/KR'}</Badge><Badge>{zh ? 'SEC+发行人原文' : 'SEC + issuer originals'}</Badge><Badge tone={C.lime}>{zh ? '正逆向估值与跟踪' : 'Valuation + monitoring'}</Badge>
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
