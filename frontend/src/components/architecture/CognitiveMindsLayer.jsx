import React, { useMemo, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SectionHeader } from '../ui/SovereignUI';

/** 🧠 COGNITIVE MIND LAYER v1.0-beta-beta — Large readable mind cards */

const MIND_META = {
  architect:  { icon: '🏛️', color: '#00e5ff', label: 'Architect',   role: 'System Designer' },
  ghost:      { icon: '👻', color: '#ff3366', label: 'Ghost Guard', role: 'Risk Sentinel' },
  ultrathink: { icon: '🧠', color: '#d4a5ff', label: 'Ultrathink',  role: 'Deep Reasoning' },
  evolution:  { icon: '🧬', color: '#00ffaa', label: 'Evolution',   role: 'Self-Adaptation' },
  observer:   { icon: '👁️', color: '#ffcc00', label: 'Observer',    role: 'Market Watch' },
  experiment: { icon: '🧪', color: '#4d7fff', label: 'Experiment',  role: 'Hypothesis' },
  system:     { icon: '💻', color: '#8899ac', label: 'Sovereign OS',role: 'Core Daemon' },
};

const FALLBACK = { architect: 'SYNCHRONIZED', evolution: 'SYNCHRONIZED', observer: 'SYNCHRONIZED', experiment: 'SYNCHRONIZED', ultrathink: 'SYNCHRONIZED', system: 'SYNCHRONIZED', ghost: 'SYNCHRONIZED' };

function hexToRgb(hex) {
  if (!hex || !hex.startsWith('#')) return '255,255,255';
  return [parseInt(hex.slice(1,3),16), parseInt(hex.slice(3,5),16), parseInt(hex.slice(5,7),16)].join(',');
}

export default function CognitiveMindsLayer({ brain = {}, activityMap = {}, health = {} }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  const raw   = brain.minds || {};
  const src   = Object.keys(raw).length > 0 ? raw : FALLBACK;

  const minds = useMemo(() => Object.entries(src).map(([name, status]) => {
    const s       = typeof status === 'string' ? status : (status?.status || 'ACTIVE');
    const meta    = MIND_META[name.toLowerCase()] || { icon: '🧬', color: '#fff', label: name, role: 'Cognitive Entity' };
    const lastAct = activityMap[`mind_${name.toLowerCase()}`] || activityMap[name.toLowerCase()] || 0;
    const isActive  = (now - lastAct) < 1500;
    const isOnline  = ['ACTIVE','Running','NOMINAL','SYNCHRONIZED'].includes(s);
    return { name, status: s, ...meta, isActive, isOnline };
  }), [src, activityMap, now]);

  const onlineCount = minds.filter(m => m.isOnline).length;
  const activeCount = minds.filter(m => m.isActive).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* Header */}
      <div style={{
        padding: '12px 18px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(0,0,0,0.2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '16px' }}>🧠</span>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Cognitive Mind Layer
            </div>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              {onlineCount}/{minds.length} ONLINE · {activeCount} PULSING
            </div>
          </div>
        </div>
      </div>

      {/* Mind cards grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
        gap: '10px',
        padding: '12px',
      }}>
        {minds.map(mind => {
          const { color, isOnline, isActive } = mind;
          const rgb = hexToRgb(color);
          return (
            <motion.div key={mind.name}
              animate={{ scale: isActive ? 1.03 : 1 }}
              transition={{ duration: 0.3 }}
              style={{
                padding: '14px 12px',
                borderRadius: '10px',
                border: `2px solid ${isActive ? color : isOnline ? `${color}33` : 'rgba(255,255,255,0.06)'}`,
                background: isActive ? `rgba(${rgb},0.08)` : isOnline ? `rgba(${rgb},0.03)` : 'rgba(4,6,10,0.8)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
                boxShadow: isActive ? `0 0 20px rgba(${rgb},0.25), inset 0 0 10px rgba(${rgb},0.05)` : 'none',
                transition: 'all 0.4s',
                position: 'relative', overflow: 'hidden',
              }}>
              {/* Active sweep */}
              {isActive && (
                <motion.div
                  animate={{ x: ['-120%', '120%'] }}
                  transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
                  style={{ position: 'absolute', inset: 0, background: `linear-gradient(90deg, transparent, rgba(${rgb},0.15), transparent)`, pointerEvents: 'none' }}
                />
              )}

              {/* Icon with halo */}
              <div style={{ position: 'relative', width: '54px', height: '54px' }}>
                <div style={{
                  width: '100%', height: '100%', borderRadius: '50%',
                  background: isOnline ? `rgba(${rgb},0.12)` : 'rgba(0,0,0,0.5)',
                  border: `2px solid ${isOnline ? color : 'rgba(255,255,255,0.08)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: isActive ? `0 0 18px rgba(${rgb},0.4)` : isOnline ? `0 0 6px rgba(${rgb},0.2)` : 'none',
                  transition: 'all 0.4s',
                }}>
                  <span style={{ fontSize: '24px', filter: isOnline ? 'none' : 'grayscale(1)' }}>{mind.icon}</span>
                </div>
                {/* Rotating halo ring */}
                {isActive && (
                  <svg style={{ position: 'absolute', top: -5, left: -5, width: '64px', height: '64px', transform: 'rotate(-90deg)', pointerEvents: 'none' }}>
                    <motion.circle cx="32" cy="32" r="30" fill="none" stroke={color} strokeWidth="1.5" strokeDasharray="6 18"
                      initial={{ opacity: 0.3 }}
                      animate={{ strokeDashoffset: [-60, 0], opacity: [0.3, 0.9, 0.3] }}
                      transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                    />
                  </svg>
                )}
              </div>

              {/* Label + role */}
              <div style={{ textAlign: 'center', width: '100%' }}>
                <div style={{ fontSize: '0.68rem', fontWeight: 900, color: isOnline ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {mind.label}
                </div>
                <div style={{ fontSize: '0.52rem', color: isActive ? color : 'var(--dim)', fontFamily: 'JetBrains Mono', marginTop: '2px' }}>
                  {mind.role}
                </div>
              </div>

              {/* Status indicator */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', width: '100%', justifyContent: 'center' }}>
                <div style={{
                  width: 7, height: 7, borderRadius: '50%',
                  background: isOnline ? (isActive ? color : `${color}77`) : '#ff4444',
                  boxShadow: isOnline && isActive ? `0 0 8px ${color}` : 'none',
                }} className={isActive ? 'pulse' : ''} />
                <span style={{ fontSize: '0.58rem', fontWeight: 900, fontFamily: 'JetBrains Mono', color: isOnline ? (isActive ? color : 'var(--emerald)') : 'var(--red)' }}>
                  {isActive ? 'PULSING' : isOnline ? 'SYNCED' : 'OFFLINE'}
                </span>
              </div>

              {/* Activity bar */}
              {isOnline && (
                <div style={{ width: '100%', height: '3px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                  <motion.div
                    animate={{ width: isActive ? '100%' : '8%' }}
                    transition={{ duration: 1.2, repeat: isActive ? Infinity : 0 }}
                    style={{ height: '100%', background: color, boxShadow: `0 0 4px ${color}`, borderRadius: '2px' }}
                  />
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
