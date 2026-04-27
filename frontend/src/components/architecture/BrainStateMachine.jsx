import React, { useMemo, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

/** 🧠 SOVEREIGN NEURAL LOOP V4.0 — Vertical stepper, width-independent */

const STATES = [
  { id: 'STANDBY',    icon: '⏸️', color: '#8899ac', sub: 'Idle · Awaiting Signal' },
  { id: 'SCANNING',   icon: '🔍', color: '#00e5ff', sub: 'Probing Market Structure' },
  { id: 'ANALYZING',  icon: '🧠', color: '#d4a5ff', sub: 'Cognitive Reasoning' },
  { id: 'POSITIONED', icon: '📈', color: '#ffcc00', sub: 'Position Execution' },
  { id: 'EXIT',       icon: '🚪', color: '#00ffaa', sub: 'Harvest & Reset' },
  { id: 'EMERGENCY',  icon: '🚨', color: '#ff3366', sub: 'HALT — Risk Breach' },
];

const FLOW = ['STANDBY', 'SCANNING', 'ANALYZING', 'POSITIONED', 'EXIT'];

export default function BrainStateMachine({ brain = {}, activityMap = {} }) {
  const current   = (brain.state ?? 'STANDBY').toUpperCase();
  const [tick, setTick] = useState(0);

  const confidence = useMemo(() => {
    // V3.1: Strict Telemetry Mapping — No Aesthetic Interpolation
    if (typeof brain.confidence === 'number') return brain.confidence * 100;
    
    // Fallback logic remains, but simulation jitter removed to prevent risk misinterpretation
    const activity = Object.values(activityMap).filter(ts => Date.now() - ts < 1000).length;
    return Math.min(100, 40 + activity * 15); 
  }, [brain.confidence, activityMap]);

  useEffect(() => {
    // Interval remains to drive tick state for other micro-animations if needed
    const t = setInterval(() => setTick(p => p + 1), 200);
    return () => clearInterval(t);
  }, []);

  const activeIdx   = FLOW.indexOf(current);
  const curState    = STATES.find(s => s.id === current) || STATES[0];
  const progressPct = activeIdx >= 0 ? ((activeIdx + 1) / FLOW.length) * 100 : 0;
  const isEmg       = current === 'EMERGENCY';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'rgba(0,0,0,0.45)', overflow: 'hidden' }}>

      {/* ── Header ── */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className="pulse" style={{ width: 8, height: 8, borderRadius: '50%', background: curState.color, boxShadow: `0 0 10px ${curState.color}`, flexShrink: 0 }} />
          <span style={{ fontSize: '0.72rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Neural Loop
          </span>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.48rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Confidence</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 900, color: 'var(--cyan)', fontFamily: 'JetBrains Mono' }}>
              {confidence.toFixed(1)}%
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.48rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>State</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 900, fontFamily: 'JetBrains Mono', color: curState.color, maxWidth: '90px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {current}
            </div>
          </div>
        </div>
      </div>

      {/* ── Vertical stepper ── */}
      <div style={{ flex: 1, padding: '14px 16px 10px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0' }}>
        {FLOW.map((sid, i) => {
          const s        = STATES.find(x => x.id === sid);
          const isActive = sid === current;
          const isPast   = activeIdx > i;
          const isLast   = i === FLOW.length - 1;

          return (
            <div key={sid} style={{ display: 'flex', gap: '12px', alignItems: 'stretch' }}>

              {/* Left: circle + connector line */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '36px', flexShrink: 0 }}>
                {/* Step circle */}
                <motion.div
                  animate={{ scale: isActive ? 1.12 : 1 }}
                  style={{
                    width: 36, height: 36,
                    borderRadius: '50%',
                    border: `2px solid ${isActive ? s.color : isPast ? `${s.color}55` : 'rgba(255,255,255,0.1)'}`,
                    background: isActive ? `${s.color}18` : isPast ? `${s.color}0a` : 'rgba(4,6,10,0.9)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: isActive ? `0 0 14px ${s.color}55` : 'none',
                    transition: 'all 0.4s',
                    position: 'relative',
                    flexShrink: 0,
                  }}>
                  {/* Active pulse ring */}
                  {isActive && (
                    <motion.div
                      initial={{ scale: 1, opacity: 0.6 }}
                      animate={{ scale: 2, opacity: 0 }}
                      transition={{ duration: 1.4, repeat: Infinity }}
                      style={{
                        position: 'absolute', inset: 0, borderRadius: '50%',
                        border: `1px solid ${s.color}`,
                      }}
                    />
                  )}
                  <span style={{ fontSize: '15px', filter: isActive ? 'none' : isPast ? 'none' : 'grayscale(0.8) opacity(0.5)' }}>
                    {isPast ? '✓' : s.icon}
                  </span>
                </motion.div>

                {/* Connector line to next step */}
                {!isLast && (
                  <div style={{
                    flex: 1, width: '2px', minHeight: '10px',
                    background: isPast ? `${s.color}55` : 'rgba(255,255,255,0.06)',
                    borderRadius: '1px',
                    margin: '2px 0',
                    transition: 'background 0.4s',
                  }} />
                )}
              </div>

              {/* Right: state info */}
              <div style={{
                flex: 1,
                paddingBottom: isLast ? 0 : '12px',
                paddingTop: '6px',
                display: 'flex', flexDirection: 'column', gap: '2px',
              }}>
                <motion.div
                  animate={{ x: isActive ? 2 : 0 }}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    fontSize: '0.68rem', fontWeight: 900, fontFamily: 'Outfit',
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    color: isActive ? '#fff' : isPast ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.22)',
                    transition: 'color 0.3s',
                  }}>
                    {sid}
                  </span>
                  {isActive && (
                    <span style={{
                      fontSize: '0.45rem', fontWeight: 900, fontFamily: 'JetBrains Mono',
                      color: s.color, background: `${s.color}18`,
                      padding: '2px 6px', borderRadius: '4px',
                      textTransform: 'uppercase', letterSpacing: '0.08em',
                    }}>
                      ACTIVE
                    </span>
                  )}
                </motion.div>
                <span style={{
                  fontSize: '0.52rem', color: isActive ? `${s.color}cc` : 'var(--dim)',
                  fontFamily: 'JetBrains Mono', transition: 'color 0.3s',
                }}>
                  {s.sub}
                </span>

                {/* Active sweep bar */}
                {isActive && (
                  <div style={{ height: '2px', background: 'rgba(255,255,255,0.05)', borderRadius: '1px', overflow: 'hidden', marginTop: '4px', width: '100%' }}>
                    <motion.div
                      animate={{ x: ['-100%', '200%'] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
                      style={{ width: '40%', height: '100%', background: `linear-gradient(90deg, transparent, ${s.color}, transparent)`, borderRadius: '1px' }}
                    />
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* EMERGENCY strip */}
        <div style={{
          marginTop: '10px',
          padding: '8px 12px', borderRadius: '8px',
          border: `1.5px solid ${isEmg ? '#ff3366' : 'rgba(255,51,102,0.12)'}`,
          background: isEmg ? 'rgba(255,51,102,0.12)' : 'rgba(255,51,102,0.02)',
          display: 'flex', alignItems: 'center', gap: '10px',
          boxShadow: isEmg ? '0 0 20px rgba(255,51,102,0.3)' : 'none',
          transition: 'all 0.4s', flexShrink: 0,
        }}>
          <span style={{ fontSize: '16px', flexShrink: 0 }}>🚨</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.6rem', fontWeight: 900, color: isEmg ? '#ff3366' : 'rgba(255,51,102,0.35)', fontFamily: 'Outfit', textTransform: 'uppercase' }}>
              Emergency Override
            </div>
            <div style={{ fontSize: '0.52rem', color: isEmg ? 'rgba(255,255,255,0.8)' : 'var(--dim)', fontFamily: 'JetBrains Mono', marginTop: '1px' }}>
              {isEmg ? '⚠️ HALT — Risk threshold breached' : 'Monitoring risk threshold'}
            </div>
          </div>
          {isEmg && <div className="pulse" style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff3366', boxShadow: '0 0 12px #ff3366', flexShrink: 0 }} />}
        </div>
      </div>

      {/* ── Progress bar ── */}
      <div style={{ padding: '8px 16px 12px', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '0.48rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Cycle Progress</span>
          <span style={{ fontSize: '0.58rem', color: 'var(--cyan)', fontFamily: 'JetBrains Mono', fontWeight: 900 }}>{progressPct.toFixed(0)}%</span>
        </div>
        <div style={{ height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
          <motion.div
            animate={{ width: `${progressPct}%` }}
            style={{ height: '100%', background: 'linear-gradient(90deg, var(--cyan), var(--emerald))', boxShadow: '0 0 8px var(--cyan)', borderRadius: '2px' }}
            transition={{ duration: 0.6 }}
          />
        </div>
      </div>
    </div>
  );
}
