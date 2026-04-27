import React, { useMemo, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/** 🌀 Dhatu Oracle Causation Map v1.0-beta-beta — 3-column HTML layout, large readable cards */

const INPUT_NODES = [
  { id: 'Yields',     icon: '📈', color: '#ffb700', desc: 'Bond Yields' },
  { id: 'Oil',        icon: '🛢️', color: '#888888', desc: 'Crude WTI' },
  { id: 'DXY',        icon: '💵', color: '#00d4ff', desc: 'Dollar Index' },
  { id: 'VIX',        icon: '🌡️', color: '#ff2b5e', desc: 'Fear Gauge' },
  { id: 'News',       icon: '📰', color: '#c084fc', desc: 'Sentiment' },
];

const OUTPUT_NODES = [
  { id: 'Technicals', icon: '🧬', color: '#0ea5e9', desc: 'TA Signals' },
  { id: 'Macro',      icon: '📊', color: '#00ff88', desc: 'Macro Regime' },
  { id: 'SPY',        icon: '🏛️', color: '#00ff88', desc: 'S&P500 ETF' },
  { id: 'QQQ',        icon: '🏛️', color: '#c084fc', desc: 'NASDAQ ETF' },
];

const REGIME_COLORS = {
  BULLISH: '#00ff88', BEARISH: '#ff2b5e', NEUTRAL: '#ffcc00',
  RISK_ON: '#00ff88', RISK_OFF: '#ff2b5e', DEFAULT: '#d4a5ff',
};

export default function OracleCausationGraph({ oracle = {}, activityMap = {} }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  const dominating  = oracle.theme || oracle.dhatu || 'NEUTRAL';
  const confidence  = Math.max(0, Math.min(1, oracle.confidence || 0));
  const oracleLast  = activityMap['oracle'] || activityMap['oracle.state'] || 0;
  const isLive      = (now - oracleLast) < 3000;

  const regimeColor = REGIME_COLORS[dominating.toUpperCase()] || REGIME_COLORS.DEFAULT;
  const confPct     = (confidence * 100).toFixed(0);

  // Confidence ring geometry
  const ringR  = 38;
  const ringC  = 2 * Math.PI * ringR;
  const filled = ringC * confidence;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* ── Header ── */}
      <div style={{
        padding: '12px 18px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(0,0,0,0.2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '16px' }}>🌀</span>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Dhatu Oracle Causation Map
            </div>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              CAUSAL INFERENCE ENGINE · Samvid v1.0-beta-beta-beta
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.5rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Regime</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 900, color: regimeColor, fontFamily: 'JetBrains Mono' }}>
              {dominating.toString().toUpperCase().slice(0, 12)}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.5rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Confidence</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 900, color: 'var(--violet)', fontFamily: 'JetBrains Mono' }}>
              {confPct}%
            </div>
          </div>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: isLive ? 'var(--emerald)' : 'var(--dim)',
            boxShadow: isLive ? '0 0 10px var(--emerald)' : 'none',
          }} className={isLive ? 'pulse' : ''} />
        </div>
      </div>

      {/* ── 3-Column Layout ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 220px 1fr',
        gap: '0',
        padding: '20px 20px',
        alignItems: 'center',
        minHeight: '320px',
      }}>

        {/* ── LEFT: Input Nodes ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '0.52rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '2px', fontFamily: 'JetBrains Mono', textAlign: 'center', marginBottom: '4px' }}>
            INPUTS
          </div>
          {INPUT_NODES.map((node, i) => {
            // v1.0-beta-beta: Strict Data Integrity — Removing fake index-based 'activity' pulses.
            // Nodes are marked as active only when the system is LIVE and receiving oracle updates.
            const nodeActive = isLive; 
            return (
              <motion.div key={node.id}
                animate={{ scale: nodeActive ? 1.02 : 1 }}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  border: `1.5px solid ${nodeActive ? node.color : `${node.color}33`}`,
                  background: nodeActive ? `${node.color}10` : 'rgba(6,9,16,0.8)',
                  boxShadow: nodeActive ? `0 0 12px ${node.color}30` : 'none',
                  transition: 'all 0.4s',
                }}>
                <span style={{ fontSize: '18px', filter: nodeActive ? 'none' : 'grayscale(0.6)' }}>{node.icon}</span>
                <div>
                  <div style={{ fontSize: '0.65rem', fontWeight: 900, color: nodeActive ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {node.id}
                  </div>
                  <div style={{ fontSize: '0.52rem', color: nodeActive ? node.color : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
                    {node.desc}
                  </div>
                </div>
                {/* Arrow indicator */}
                <div style={{ marginLeft: 'auto', fontSize: '0.7rem', color: nodeActive ? node.color : 'rgba(255,255,255,0.15)', fontWeight: 900 }}>›</div>
              </motion.div>
            );
          })}
        </div>

        {/* ── CENTER: Oracle Core ── */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', padding: '0 8px' }}>
          <div style={{ fontSize: '0.52rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '2px', fontFamily: 'JetBrains Mono' }}>
            ORACLE
          </div>

          {/* Confidence ring */}
          <div style={{ position: 'relative', width: '120px', height: '120px' }}>
            <svg width="120" height="120" viewBox="0 0 120 120">
              {/* Background ring */}
              <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(212,165,255,0.1)" strokeWidth="7" />
              {/* Fill ring */}
              <motion.circle
                cx="60" cy="60" r="50"
                fill="none"
                stroke="var(--violet)"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 50 * confidence} ${2 * Math.PI * 50}`}
                transform="rotate(-90 60 60)"
                style={{ filter: 'drop-shadow(0 0 8px var(--violet))' }}
                animate={{ strokeDasharray: `${2 * Math.PI * 50 * confidence} ${2 * Math.PI * 50}` }}
                transition={{ duration: 1.2 }}
              />
              {/* Pulse ring when live */}
              {isLive && (
                <motion.circle
                  cx="60" cy="60" r="50"
                  fill="none" stroke="var(--violet)" strokeWidth="1.5"
                  initial={{ r: 50, opacity: 0.5 }}
                  animate={{ r: 64, opacity: 0 }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
            </svg>
            {/* Center content */}
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{ fontSize: '28px' }}>🔮</span>
              <div style={{ fontSize: '0.9rem', fontWeight: 900, color: 'var(--violet)', fontFamily: 'JetBrains Mono' }}>
                {confPct}%
              </div>
            </div>
          </div>

          {/* Regime badge */}
          <div style={{
            padding: '6px 14px',
            borderRadius: '20px',
            border: `1.5px solid ${regimeColor}55`,
            background: `${regimeColor}12`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '0.62rem', fontWeight: 900, color: regimeColor, fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>
              {dominating}
            </div>
          </div>

          {/* Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isLive ? 'var(--emerald)' : 'var(--dim)',
              boxShadow: isLive ? '0 0 6px var(--emerald)' : 'none',
            }} />
            <span style={{ fontSize: '0.55rem', fontWeight: 900, color: isLive ? 'var(--emerald)' : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              {isLive ? 'ORACLE LIVE' : 'STANDBY'}
            </span>
          </div>

          {/* Vertical connector lines */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', marginTop: 'auto' }}>
            {[0,1,2].map(i => (
              <motion.div key={i} style={{
                width: 2, height: 6, borderRadius: 1,
                background: isLive ? 'var(--violet)' : 'rgba(255,255,255,0.1)',
              }}
                animate={isLive ? { opacity: [0.2, 1, 0.2] } : {}}
                transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
              />
            ))}
          </div>
        </div>

        {/* ── RIGHT: Output Nodes ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '0.52rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '2px', fontFamily: 'JetBrains Mono', textAlign: 'center', marginBottom: '4px' }}>
            OUTPUTS
          </div>
          {OUTPUT_NODES.map((node, i) => {
            // v1.0-beta-beta: Strict Data Integrity — Removing fake index-based 'activity' pulses.
            const nodeActive = isLive;
            return (
              <motion.div key={node.id}
                animate={{ scale: nodeActive ? 1.02 : 1 }}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  border: `1.5px solid ${nodeActive ? node.color : `${node.color}33`}`,
                  background: nodeActive ? `${node.color}10` : 'rgba(6,9,16,0.8)',
                  boxShadow: nodeActive ? `0 0 12px ${node.color}30` : 'none',
                  transition: 'all 0.4s',
                }}>
                {/* Arrow indicator */}
                <div style={{ fontSize: '0.7rem', color: nodeActive ? node.color : 'rgba(255,255,255,0.15)', fontWeight: 900 }}>‹</div>
                <span style={{ fontSize: '18px', filter: nodeActive ? 'none' : 'grayscale(0.6)' }}>{node.icon}</span>
                <div>
                  <div style={{ fontSize: '0.65rem', fontWeight: 900, color: nodeActive ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {node.id}
                  </div>
                  <div style={{ fontSize: '0.52rem', color: nodeActive ? node.color : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
                    {node.desc}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
