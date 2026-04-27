import React from 'react';
import { GlassPanel, SectionHeader, DataRow } from '../ui/SovereignUI';
import { fmtMs } from '../SharedUI';

// Smart percent formatter: if value > 1, treat as already-percent (e.g. 58 → "58.0")
// If value ≤ 1, multiply by 100 (e.g. 0.58 → "58.0")
const fmtPct = (v, dec = 0) => {
  const n = Number(v);
  if (isNaN(n)) return '0.0';
  // v1.0-beta-beta: Heuristic inference: If value is small (≤ 2.0), treat as a fraction (e.g. 0.58 -> 58%, 1.1 -> 110%).
  // If value > 2.0, assume the backend already provided a percentage value.
  const pct = (n >= 0 && n <= 2.0) ? n * 100 : n;
  return pct.toFixed(dec);
};

/** 🦾 Agentic Nerve Center (Sidebar Modules - v1.0-beta-beta) */

export function SidebarHeader({ connected, sysTime, uptime }) {
  return (
    <GlassPanel style={{ borderLeft: '2px solid var(--cyan)', background: 'rgba(0,0,0,0.6)', padding: '16px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '16px' }}>
        <div className="font-outfit fw-900 c-top" style={{ fontSize: '1.25rem', lineHeight: '1.2', letterSpacing: '-0.03em' }}>SAMVID</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="c-cyan fw-900 font-outfit" style={{ fontSize: '1.4rem', letterSpacing: '-0.03em' }}>MATRIX</span>
          <span className="badge-sovereign c-red" style={{ border: '1px solid rgba(255,43,94,0.4)' }}>v1.0-beta-beta</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
        <DataRow label="Neural Link"  value={connected ? '100Hz SYNC' : 'OFFLINE'}    color={connected ? 'emerald' : 'red'} />
        <DataRow label="Server Time"  value={sysTime || '---'}                          color="top" />
        <DataRow label="Uptime"       value={fmtMs(uptime)}                             color="cyan" />
      </div>
    </GlassPanel>
  );
}

/** Full-detail agent cards A/B/C */
export function AgentStack({ brain = {}, oracle = {} }) {
  const agents = [
    {
      label: 'A: GATEKEEPER', color: 'cyan', icon: '🛡️',
      stats: [
        { label: 'Neural Cycle', val: brain.scan_stats?.cycle ?? 0 },
        { label: 'Scanned Syms', val: brain.scan_stats?.scanned ?? 0 },
        { label: 'Active Regime', val: brain.regime ?? 'PENDING', c: 'amber' }
      ]
    },
    {
      label: 'B: CLASSIFIER', color: 'violet', icon: '🔮',
      stats: [
        { label: 'Dhatu Pulse',  val: oracle.dhatu ?? 'Normal', c: 'violet' },
        { label: 'Mod Ratio',    val: (() => { const m = Number(brain.agents?.agent_b?.modifier); return `${(isNaN(m) ? 100 : (m > 1 ? m : m * 100)).toFixed(0)}%`; })() },
        { label: 'Logic Guard',  val: brain.agents?.agent_b?.freeze ? 'FREEZE' : 'AUTO', c: brain.agents?.agent_b?.freeze ? 'red' : 'dim' }
      ]
    },
    {
      label: 'C: EXECUTOR', color: 'amber', icon: '⚔️',
      stats: [
        { label: 'MT5 Interface', val: brain.agents?.agent_c?.mt5 ?? 'Offline', c: brain.agents?.agent_c?.mt5 === 'Connected' ? 'emerald' : 'dim' },
        { label: 'Black Swan',   val: brain.agents?.agent_c?.blackswan ?? 'STANDBY', c: 'cyan' },
        { label: 'Risk Vault',   val: brain.agents?.agent_c?.guard ?? '20% Rsv' }
      ]
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {agents.map((agent, i) => (
        <GlassPanel key={i} style={{ borderLeft: `2px solid var(--${agent.color})`, paddingBottom: '8px' }}>
          <SectionHeader title={agent.label} icon={agent.icon} />
          <div style={{ padding: '8px', paddingTop: '0' }}>
            {agent.stats.map((s, si) => (
              <DataRow key={si} label={s.label} value={s.val} color={s.c || 'top'} />
            ))}
          </div>
        </GlassPanel>
      ))}
    </div>
  );
}

/** Daily risk budget panel — shows brain.gap.budget */
export function BudgetPanel({ budget = {} }) {
  const regime = budget.regime ?? 'UNKNOWN';
  const regimeColor = regime === 'BULL' ? 'emerald' : regime === 'BEAR' ? 'red' : regime === 'VOLATILE' ? 'amber' : 'dim';

  return (
    <GlassPanel style={{ borderLeft: '2px solid var(--amber)' }}>
      <SectionHeader title="Daily Risk Budget" icon="📋" sub="Morning Budget Gate" />
      <div style={{ padding: '8px', paddingTop: '0' }}>
        <DataRow label="Max Trades"   value={budget.max_trades   ?? '---'} color="top" />
        <DataRow label="Min Catalyst" value={budget.min_catalyst != null ? `${fmtPct(budget.min_catalyst)}%` : '---'} color="cyan" />
        <DataRow label="Max Risk/Trade" value={budget.max_risk   != null ? `${fmtPct(budget.max_risk, 1)}%` : '---'} color="amber" />
        <DataRow label="Regime"       value={regime}                        color={regimeColor} />
      </div>
    </GlassPanel>
  );
}
