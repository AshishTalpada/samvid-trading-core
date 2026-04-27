import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/** 🧠 SOVEREIGN COGNITIVE MATRIX V2.6 | REAL-TIME MIND LAYER */

const MINDS_CONFIG = [
  { id: 'architect',  label: 'Architect',  desc: 'Neural Topology Engine',        color: '#00e5ff', icon: '💎' },
  { id: 'evolution',  label: 'Evolution',  desc: 'Genetic Agent Optimizer',       color: '#d4a5ff', icon: '🧬' },
  { id: 'observer',   label: 'Observer',   desc: 'Recursive Consensus Auditor',   color: '#4d7fff', icon: '👁️' },
  { id: 'experiment', label: 'Experiment', desc: 'Stochastic Logic Prober',       color: '#00ffaa', icon: '🧪' },
  { id: 'ultrathink', label: 'Ultrathink', desc: 'Deep Context Compression',      color: '#ffcc00', icon: '🧠' },
  { id: 'system',     label: 'System',     desc: 'Core Resource Orchestrator',    color: '#8899ac', icon: '⚙️' },
  { id: 'ghost',      label: 'Ghost',      desc: 'Sovereign Guard Mode',          color: '#ff3366', icon: '👻' },
];

const FALLBACK_MINDS = Object.fromEntries(MINDS_CONFIG.map(m => [m.id, 'SYNCHRONIZED']));

export default function QuantumMinds({ minds = {}, activityMap = {}, eventQueue = [] }) {
  const activeMinds = (minds && Object.keys(minds).length > 0) ? minds : FALLBACK_MINDS;

  const mindMetrics = useMemo(() => {
    const now = Date.now();
    return MINDS_CONFIG.map(m => {
      const raw      = activeMinds?.[m.id];
      const status   = raw?.status || (typeof raw === 'string' ? raw : 'OFFLINE');
      const isActive = (now - (activityMap[`mind_${m.id}`] || 0)) < 2000;
      const lastEvent = eventQueue?.find(e => e.source === `mind_${m.id}` || e.subtype === m.id);
      return { ...m, status, isActive, lastEvent };
    });
  }, [minds, activityMap, eventQueue]);

  return (
    <div style={{
      background: 'rgba(0,0,0,0.6)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '10px',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        background: 'rgba(0,0,0,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ position: 'relative' }}>
            <div className="pulse" style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--violet)', boxShadow: '0 0 10px var(--violet)' }} />
          </div>
          <span className="fw-900 uppercase c-top font-outfit" style={{ fontSize: '0.6rem', letterSpacing: '0.12em' }}>Sovereign Cognitive Matrix</span>
        </div>
        <span className="font-mono c-violet fw-900" style={{ fontSize: '0.5rem', letterSpacing: '-0.02em' }}>V13.6 ALPHA-7</span>
      </div>

      {/* Mind rows */}
      <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: 450, overflowY: 'auto' }}>
        {mindMetrics.map((m) => {
          const isAlive = m.status === 'ACTIVE' || m.status === 'SYNCHRONIZED';
          return (
            <motion.div
              key={m.id}
              initial={false}
              animate={{
                background: m.isActive ? `${m.color}08` : 'rgba(255,255,255,0.02)',
                borderColor: m.isActive ? `${m.color}44` : 'rgba(255,255,255,0.05)',
              }}
              style={{
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', flexDirection: 'column', gap: '4px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {/* Status dot */}
                  <div style={{ position: 'relative' }}>
                    <div style={{
                      width: '8px', height: '8px', borderRadius: '50%',
                      background: isAlive ? m.color : '#3a4a60',
                      boxShadow: isAlive ? `0 0 8px ${m.color}` : 'none',
                    }} />
                    {m.isActive && (
                      <motion.div
                        initial={{ scale: 1, opacity: 1 }}
                        style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: m.color }}
                        animate={{ scale: [1, 2.5], opacity: [1, 0] }}
                        transition={{ repeat: Infinity, duration: 1 }}
                      />
                    )}
                  </div>
                  <div>
                    <div className="fw-900 c-top font-outfit" style={{ fontSize: '0.62rem', letterSpacing: '0.05em' }}>
                      {m.icon} {m.label}
                      <span style={{ opacity: 0.3, fontSize: '0.5rem', marginLeft: '6px' }}>#{m.id.slice(0, 3)}</span>
                    </div>
                  </div>
                </div>
                <span className="fw-900 font-mono" style={{ fontSize: '0.55rem', color: isAlive ? 'var(--emerald)' : 'var(--red)' }}>
                  {m.status}
                </span>
              </div>

              <div style={{ fontSize: '0.57rem', color: 'var(--dim)', paddingLeft: '18px', lineHeight: 1 }}>
                {m.desc}
              </div>

              {m.isActive && m.lastEvent && (
                <motion.div
                  initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }}
                  style={{
                    marginLeft: '18px', marginTop: '2px',
                    fontSize: '0.52rem', fontFamily: 'JetBrains Mono, monospace', color: 'var(--cyan)',
                    background: 'rgba(0,229,255,0.05)', borderLeft: '2px solid rgba(0,229,255,0.4)',
                    padding: '2px 6px', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
                  }}
                >
                  {m.lastEvent.message}
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Footer — live convergence from real mind statuses */}
      {(() => {
        const totalMinds  = mindMetrics.length;
        const activeCount = mindMetrics.filter(m => m.status === 'ACTIVE' || m.status === 'SYNCHRONIZED').length;
        const convergence = totalMinds > 0 ? ((activeCount / totalMinds) * 100).toFixed(0) : 0;
        const pulsing     = mindMetrics.filter(m => m.isActive).length;
        return (
          <div style={{
            padding: '8px 12px',
            borderTop: '1px solid rgba(255,255,255,0.05)',
            background: 'rgba(0,0,0,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.45rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Active Minds</span>
                <span className="font-mono fw-900 c-top" style={{ fontSize: '0.6rem' }}>
                  {activeCount} / {totalMinds}
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.45rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Convergence</span>
                <span className="font-mono fw-900 c-emerald" style={{ fontSize: '0.6rem' }}>
                  {convergence}%
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.45rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Pulsing</span>
                <span className="font-mono fw-900 c-cyan" style={{ fontSize: '0.6rem' }}>{pulsing}</span>
              </div>
            </div>
            <div className={pulsing > 0 ? 'pulse' : ''}
              style={{ width: 8, height: 8, borderRadius: '50%', background: pulsing > 0 ? 'var(--emerald)' : 'var(--dim)', opacity: 0.6 }} />
          </div>
        );
      })()}
    </div>
  );
}
