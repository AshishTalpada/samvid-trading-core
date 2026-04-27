import React from 'react';
import { motion } from 'framer-motion';
import { Sparkline, fmt } from './SharedUI';
import { GlassPanel, StatusBadge, DataRow } from './ui/SovereignUI';

/** 🏛️ STAT CARDS v1.0-beta-beta | COGNITIVE HUD
 *  Top-row metrics: Dhatu Oracle · Execution State · Session P&L · SPY · QQQ · IWM
 */

const DHATU_THEMES = {
  Vriddhi:  { color: 'var(--cyan)',    glow: true },
  Kshaya:   { color: 'var(--red)',     glow: true },
  Chala:    { color: 'var(--amber)',   glow: true },
  Viyoga:   { color: 'var(--violet)',  glow: true },
  Sthira:   { color: 'var(--emerald)', glow: true },
  Abhava:   { color: 'var(--red)',     glow: true },
  Samyoga:  { color: 'var(--cyan)',    glow: true },
  Sthiti:   { color: 'var(--mid)',     glow: true },
  NEUTRAL:  { color: 'var(--dim)',     glow: false },
};

const getDhatuTheme = (s) => DHATU_THEMES[s] ?? DHATU_THEMES.NEUTRAL;

const MetricHeader = ({ label, badge, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
    <span className="fw-900 c-dim uppercase ls-wider" style={{ fontSize: '0.62rem', letterSpacing: '0.2em' }}>{label}</span>
    <StatusBadge label={badge} color={color} />
  </div>
);

const MetricValue = ({ value, color, glow }) => (
  <div style={{
    fontSize: '1.6rem', fontWeight: 900, color,
    margin: '4px 0',
    textShadow: glow ? `0 0 15px ${color}44` : 'none',
    fontFamily: 'Outfit, sans-serif',
    letterSpacing: '-0.02em',
  }}>
    {value}
  </div>
);

const PriceMetric = ({ symbol, marketData, tickData, color }) => {
  const data      = marketData || [];
  const latest    = data.length ? data[data.length - 1] : null;

  // Price: prefer live tick, then last bar close
  const price     = tickData?.price ?? latest?.close ?? null;

  // Change: prefer tick change_pct, then compute from last two bars
  const rawChange = tickData?.change_pct != null
    ? tickData.change_pct * (Math.abs(tickData.change_pct) > 1 ? 1 : 100) // normalise if already pct
    : (data.length > 1 && latest?.close != null && data[data.length - 2]?.close != null)
      ? ((latest.close - data[data.length - 2].close) / data[data.length - 2].close) * 100
      : null;

  const hasChange = rawChange != null;
  const change    = rawChange ?? 0;
  const isUp      = change >= 0;

  // High / Low: prefer tick data, then latest bar
  const high = tickData?.high ?? latest?.high ?? null;
  const low  = tickData?.low  ?? latest?.low  ?? null;

  return (
    <GlassPanel style={{ borderLeft: `2px solid ${color}`, padding: '12px', minHeight: '110px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <span className="fw-900 c-top" style={{ fontSize: '0.9rem' }}>{symbol}</span>
          <div className={`fw-900 font-mono ${price != null ? (isUp ? 'c-emerald' : 'c-red') : 'c-dim'}`} style={{ fontSize: '1.05rem', marginTop: '2px' }}>
            {price != null ? `$${fmt(price)}` : '---'}
          </div>
        </div>
        <Sparkline data={data.slice(-20)} color={color} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
        {hasChange ? (
          <span className={`fw-900 font-mono ${isUp ? 'c-emerald' : 'c-red'}`}
            style={{ fontSize: '0.6rem', background: isUp ? 'rgba(0,255,170,0.05)' : 'rgba(255,51,102,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
            {isUp ? '▲' : '▼'} {fmt(Math.abs(change), 2)}%
          </span>
        ) : (
          <span className="font-mono c-dim" style={{ fontSize: '0.6rem', padding: '2px 6px' }}>-- %</span>
        )}
        <div style={{ display: 'flex', gap: '8px' }}>
          <span className="font-mono c-dim" style={{ fontSize: '0.55rem' }}>H:{high != null ? fmt(high) : '--'}</span>
          <span className="font-mono c-dim" style={{ fontSize: '0.55rem' }}>L:{low  != null ? fmt(low)  : '--'}</span>
        </div>
      </div>
    </GlassPanel>
  );
};

export default function StatCards({ oracle, brain, market, ticks }) {
  const theme   = getDhatuTheme(oracle?.dhatu);
  const pnl     = brain?.pnl_session ?? 0;
  const pnlColor = pnl >= 0 ? 'emerald' : 'red';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>

      {/* 🔮 Dhatu Oracle */}
      <GlassPanel style={{ borderLeft: `2px solid ${theme.color}`, padding: '12px' }}>
        <MetricHeader label="Dhatu State" badge="ORACLE" color="violet" />
        <MetricValue value={oracle?.dhatu || 'STHITI'} color={theme.color} glow />
        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <DataRow label="CONF"  value={`${fmt((oracle?.confidence ?? 0) * 100, 0)}%`} color="violet" />
          <DataRow label="BIAS"  value={String(oracle?.bias || 'NEUTRAL').toUpperCase()} color="dim" />
        </div>
      </GlassPanel>

      {/* 🧠 Brain State */}
      <GlassPanel style={{ borderLeft: '2px solid var(--amber)', padding: '12px' }}>
        <MetricHeader label="Execution State" badge="BRAIN" color="amber" />
        <MetricValue value={brain?.state || 'STANDBY'} color="var(--amber)" glow />
        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <DataRow label="REGIME" value={String(brain?.regime || 'UNKNOWN').toUpperCase()} color="cyan" />
          <DataRow label="CYCLE"  value={brain?.scan_stats?.cycle || 0} color="dim" />
        </div>
      </GlassPanel>

      {/* 📊 Session P&L */}
      <GlassPanel style={{ borderLeft: `2px solid var(--${pnlColor})`, padding: '12px' }}>
        <MetricHeader label="Session P&L" badge="PROPNET" color={pnlColor} />
        <MetricValue value={`${pnl >= 0 ? '+' : ''}$${fmt(pnl, 0)}`} color={`var(--${pnlColor})`} glow />
        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <DataRow label="POSITIONS" value={brain?.positions_count || 0} color="amber" />
          <DataRow label="LOSSES"    value={brain?.consecutive_losses ?? 0} color={brain?.consecutive_losses >= 2 ? 'red' : 'dim'} />
        </div>
      </GlassPanel>

      {/* 💹 SPY */}
      <PriceMetric symbol="SPY" marketData={market?.['SPY']} tickData={ticks?.['SPY']} color="var(--cyan)" />
      {/* 💹 QQQ */}
      <PriceMetric symbol="QQQ" marketData={market?.['QQQ']} tickData={ticks?.['QQQ']} color="var(--violet)" />
      {/* 💹 IWM */}
      <PriceMetric symbol="IWM" marketData={market?.['IWM']} tickData={ticks?.['IWM']} color="var(--emerald)" />

    </div>
  );
}
