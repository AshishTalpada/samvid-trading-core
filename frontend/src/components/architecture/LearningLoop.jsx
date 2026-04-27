import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

/** 🧬 Agent D Self-Evolution Loop v1.0-beta-beta — 2×2 card grid with stats panel */

const LOOP_NODES = [
  { id: 'brain',    icon: '🧠', color: '#00ff88', label: 'Brain Core',    desc: 'Neural Engine', position: 'top-left' },
  { id: 'exit',     icon: '📦', color: '#ffcc00', label: 'Trade Exit',    desc: 'P&L Harvest',   position: 'top-right' },
  { id: 'calib',    icon: '🧬', color: '#00e5ff', label: 'Calibration',   desc: 'Param Tuning',  position: 'bottom-left' },
  { id: 'agent_d',  icon: '📖', color: '#d4a5ff', label: 'Agent D',       desc: 'Self-Evolving', position: 'bottom-right' },
];


export default function LearningLoop({ brain = {}, eventQueue = [], activityMap = {} }) {
  const [pulse, setPulse] = useState(false);
  const [cycleCount, setCycleCount] = useState(0);
  const [now, setNow] = useState(Date.now());
  const agentD = brain.agents?.agent_d || {};

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  useEffect(() => {
    if (eventQueue.length > 0 && eventQueue[0].type === 'calibration.update') {
      setPulse(true);
      setCycleCount(c => c + 1);
      const t = setTimeout(() => setPulse(false), 2500);
      return () => clearTimeout(t);
    }
  }, [eventQueue]);

  const isActive    = agentD.status === 'SYNCHRONIZED' || agentD.status === 'ACTIVE';
  const lastCalib   = activityMap['calibration.update'] || activityMap['agent_d'] || 0;
  const calibRecent = (now - lastCalib) < 5000;

  const memoryCount  = agentD.memory        ?? '—';
  const topPattern   = agentD.top_pattern   ?? 'Gathering...';
  const sigGate      = agentD.threshold_gate ?? 'OFFLINE';
  const calibStatus  = agentD.calibration   ?? 'OFFLINE';
  const winRate      = agentD.win_rate != null ? `${(agentD.win_rate * 100).toFixed(1)}%` : '—';
  const totalCycles  = agentD.cycle_count ?? cycleCount;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* ── Header ── */}
      <div style={{
        padding: '12px 18px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(0,0,0,0.2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '16px' }}>🧬</span>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Agent D · Self-Evolution Loop
            </div>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              ADAPTIVE CALIBRATION ENGINE
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.5rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Cycles</div>
            <div style={{ fontSize: '1.0rem', fontWeight: 900, color: 'var(--emerald)', fontFamily: 'JetBrains Mono' }}>
              {totalCycles}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: calibRecent ? 'var(--emerald)' : isActive ? 'rgba(0,255,136,0.4)' : 'var(--dim)',
              boxShadow: calibRecent ? '0 0 10px var(--emerald)' : 'none',
            }} className={calibRecent ? 'pulse' : ''} />
            <span style={{ fontSize: '0.62rem', fontWeight: 900, color: calibRecent ? 'var(--emerald)' : isActive ? 'var(--emerald)' : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              {calibRecent ? 'CALIBRATING' : isActive ? 'SYNCED' : 'INIT'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Main Content: Loop Grid on top, Stats below ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '14px 12px' }}>

        {/* ── Loop Grid ── */}
        <div style={{ position: 'relative' }}>
          {/* 2×2 grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
          }}>
            {LOOP_NODES.map(node => {
              const isNodeActive = calibRecent && (node.id === 'agent_d' || node.id === 'calib');
              const isBrainActive = calibRecent || isActive;
              const active = node.id === 'brain' ? isBrainActive : isNodeActive;
              return (
                <motion.div key={node.id}
                  animate={{ scale: active ? 1.04 : 1 }}
                  style={{
                    padding: '14px 10px',
                    borderRadius: '10px',
                    border: `2px solid ${active ? node.color : `${node.color}28`}`,
                    background: active ? `${node.color}0e` : 'rgba(5,7,12,0.9)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '7px',
                    boxShadow: active ? `0 0 18px ${node.color}30, inset 0 0 10px ${node.color}08` : 'none',
                    transition: 'all 0.4s',
                    position: 'relative', overflow: 'hidden',
                  }}>
                  {/* Sweep on active */}
                  {active && (
                    <motion.div
                      animate={{ x: ['-120%', '120%'] }}
                      transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
                      style={{ position: 'absolute', inset: 0, background: `linear-gradient(90deg, transparent, ${node.color}12, transparent)`, pointerEvents: 'none' }}
                    />
                  )}

                  {/* Icon circle */}
                  <div style={{
                    width: '48px', height: '48px', borderRadius: '50%',
                    background: active ? `${node.color}15` : 'rgba(0,0,0,0.5)',
                    border: `2px solid ${active ? node.color : `${node.color}33`}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: active ? `0 0 14px ${node.color}40` : 'none',
                    transition: 'all 0.4s',
                  }}>
                    <span style={{ fontSize: '22px', filter: active ? 'none' : 'grayscale(0.6)' }}>{node.icon}</span>
                  </div>

                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.65rem', fontWeight: 900, color: active ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {node.label}
                    </div>
                    <div style={{ fontSize: '0.52rem', color: active ? node.color : 'var(--dim)', fontFamily: 'JetBrains Mono', marginTop: '2px' }}>
                      {node.desc}
                    </div>
                  </div>

                  {/* Status dot */}
                  <div style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: active ? node.color : 'rgba(255,255,255,0.15)',
                    boxShadow: active ? `0 0 8px ${node.color}` : 'none',
                  }} className={active ? 'pulse' : ''} />
                </motion.div>
              );
            })}
          </div>

          {/* Center loop indicator — overlay */}
          <div style={{
            position: 'absolute',
            top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            width: '44px', height: '44px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            pointerEvents: 'none',
            zIndex: 2,
          }}>
            <svg width="44" height="44" viewBox="0 0 44 44">
              <motion.circle
                cx="22" cy="22" r="18"
                fill="none"
                stroke={calibRecent ? 'var(--emerald)' : 'rgba(255,255,255,0.12)'}
                strokeWidth="2"
                strokeDasharray="8 6"
                animate={{ rotate: 360 }}
                transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                style={{ transformOrigin: '22px 22px' }}
              />
              <text x="22" y="26" textAnchor="middle"
                fill={calibRecent ? 'var(--emerald)' : 'rgba(255,255,255,0.4)'}
                style={{ fontSize: '14px' }}>🔁</text>
            </svg>
            {pulse && (
              <motion.div
                initial={{ width: 44, height: 44, opacity: 0.8 }}
                animate={{ width: 80, height: 80, opacity: 0 }}
                transition={{ duration: 1.5 }}
                style={{
                  position: 'absolute', borderRadius: '50%',
                  border: '2px solid var(--emerald)',
                }}
              />
            )}
          </div>
        </div>

        {/* ── Stats Panel — full width horizontal grid ── */}
        <div style={{
          borderRadius: '10px',
          border: '1px solid rgba(0,255,136,0.15)',
          background: 'rgba(0,8,20,0.7)',
          overflow: 'hidden',
        }}>
          {/* Stats header */}
          <div style={{
            padding: '8px 12px',
            borderBottom: '1px solid rgba(0,255,136,0.12)',
            background: 'rgba(0,255,136,0.05)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '13px' }}>📊</span>
              <span style={{ fontSize: '0.6rem', fontWeight: 900, color: 'var(--emerald)', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Agent Metrics
              </span>
            </div>
            {/* Inline activity bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.5rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase', fontFamily: 'JetBrains Mono' }}>Evolution Activity</span>
              <div style={{ width: '80px', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                <motion.div
                  animate={{ width: calibRecent ? '100%' : isActive ? '45%' : '5%' }}
                  transition={{ duration: 1.5, repeat: calibRecent ? Infinity : 0 }}
                  style={{ height: '100%', background: 'linear-gradient(90deg, var(--emerald), var(--cyan))', borderRadius: '2px', boxShadow: '0 0 6px var(--emerald)' }}
                />
              </div>
            </div>
          </div>

          {/* Stats grid — Wrapping flex to prevent clipping */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0',
            justifyContent: 'center',
          }}>
            {[
              { label: 'Memory',      value: memoryCount, color: 'var(--cyan)',    icon: '💾' },
              { label: 'Win Rate',    value: winRate,     color: 'var(--emerald)', icon: '🎯' },
              { label: 'Top Pattern', value: topPattern,  color: 'var(--violet)',  icon: '🧬' },
              { label: 'Sig. Gate',   value: sigGate,     color: sigGate === 'OFFLINE' ? 'var(--red)' : 'var(--emerald)', icon: '🚪' },
              { label: 'Calibration', value: calibStatus, color: calibStatus === 'OFFLINE' ? 'var(--red)' : 'var(--emerald)', icon: '⚙️' },
            ].map((s, i) => (
              <div key={s.label} style={{
                padding: '10px 10px',
                flex: '1 1 95px',
                borderRight: '1px solid rgba(255,255,255,0.05)',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center',
                minWidth: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', maxWidth: '100%' }}>
                  <span style={{ fontSize: '11px' }}>{s.icon}</span>
                  <span style={{ fontSize: '0.45rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase', fontFamily: 'JetBrains Mono', letterSpacing: '0.05em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.label}
                  </span>
                </div>
                <span style={{ fontSize: '0.6rem', fontWeight: 900, color: s.color, fontFamily: 'JetBrains Mono', textAlign: 'center', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
