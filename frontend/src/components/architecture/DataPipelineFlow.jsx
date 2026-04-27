import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

/** 📡 Data Ingestion Pipeline v1.0-beta-beta — Large HTML stage cards, horizontal flow */

const SOURCES = [
  { id: 'IBKR',    icon: '⚡', rate: '100Hz', color: '#00e5ff', healthKey: 'ibkr',    desc: 'Live Feed' },
  { id: 'yFin',    icon: '📊', rate: '1Hz',   color: '#8899ac', healthKey: null,       desc: 'Historical' },
  { id: 'OpenBB',  icon: '🌐', rate: '5Hz',   color: '#d4a5ff', healthKey: null,       desc: 'Alt Data' },
  { id: 'Finnhub', icon: '📰', rate: '0.5Hz', color: '#ffcc00', healthKey: null,       desc: 'News Feed' },
];


function PipelineArrow({ active, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '0 8px' }}>
      <svg width="40" height="24" viewBox="0 0 40 24" style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id={`grad-${color}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="transparent" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <path d="M 0 12 L 32 12" stroke={active ? color : 'rgba(255,255,255,0.1)'} strokeWidth="2.5" 
          strokeDasharray={active ? 'none' : '4 4'} opacity={active ? 1 : 0.4} />
        <path d="M 30 6 L 38 12 L 30 18 Z" fill={active ? color : 'rgba(255,255,255,0.1)'} />
        {active && (
           <motion.circle cx={0} cy={12} r={3} fill="#fff"
             animate={{ cx: [0, 32], opacity: [0, 1, 0] }}
             transition={{ duration: 1.2, repeat: Infinity, ease: 'easeIn' }}
           />
        )}
      </svg>
    </div>
  );
}

export default function DataPipelineFlow({ brain = {}, health = {}, activityMap = {} }) {
  const [barCount, setBarCount] = useState(0);
  const [now, setNow] = useState(Date.now());

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  useEffect(() => {
    const pipelineAct = activityMap['pipeline'] || activityMap['candle.batch'] || 0;
    if (pipelineAct > 0 && (Date.now() - pipelineAct) < 2000) {
      setBarCount(c => c + 1);
    }
  }, [activityMap['pipeline'], activityMap['candle.batch']]);

  const ibkrOnline  = health?.components?.ibkr  === 'ONLINE' || (now - (activityMap['ibkr']    || 0)) < 3000;
  const qdbOnline   = health?.components?.qdb   === 'ONLINE' || (now - (activityMap['questdb'] || activityMap['sqlite'] || 0)) < 3000;
  const brainOnline = health?.components?.brain === 'ONLINE' || (now - (activityMap['intel_bus'] || 0)) < 3000;
  const pipeActive  = (now - (activityMap['pipeline'] || activityMap['candle.batch'] || 0)) < 3000;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* ── Header ── */}
      <div style={{
        padding: '12px 18px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(0,0,0,0.2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '16px' }}>📡</span>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Data Ingestion Pipeline
            </div>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              MULTI-SOURCE · REAL-TIME INGEST
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '20px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.5rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>Bars In</div>
            <div style={{ fontSize: '1.0rem', fontWeight: 900, color: 'var(--cyan)', fontFamily: 'JetBrains Mono' }}>{barCount}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.5rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase' }}>IBKR Feed</div>
            <div style={{ fontSize: '0.75rem', fontWeight: 900, color: ibkrOnline ? 'var(--emerald)' : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              {ibkrOnline ? '⬤ LIVE' : '○ STANDBY'}
            </div>
          </div>
        </div>
      </div>

      {/* ── Pipeline Flow ── */}
      <div style={{ padding: '16px 12px' }}>

        {/* Stage 1: Sources */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '0.52rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '2px', fontFamily: 'JetBrains Mono', marginBottom: '8px' }}>
            DATA SOURCES
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '10px' }}>
            {SOURCES.map(src => {
              const active = src.healthKey === 'ibkr' ? ibkrOnline : true;
              return (
                <motion.div key={src.id}
                  animate={{ scale: active && ibkrOnline ? 1.03 : 1 }}
                  style={{
                    padding: '10px 8px',
                    borderRadius: '8px',
                    border: `2px solid ${active ? src.color : `${src.color}22`}`,
                    background: active ? `${src.color}0e` : 'rgba(6,9,16,0.8)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
                    boxShadow: active && ibkrOnline ? `0 0 14px ${src.color}25` : 'none',
                    transition: 'all 0.4s',
                  }}>
                  <span style={{ fontSize: '20px', filter: active ? 'none' : 'grayscale(0.7)' }}>{src.icon}</span>
                  <div style={{ fontSize: '0.65rem', fontWeight: 900, color: active ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', textAlign: 'center' }}>
                    {src.id}
                  </div>
                  <div style={{ fontSize: '0.52rem', color: active ? src.color : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
                    {src.rate}
                  </div>
                  <div style={{ fontSize: '0.5rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
                    {src.desc}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Down arrow row */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px', gap: '4px' }}>
          {[0,1,2].map(i => (
            <motion.div key={i} style={{
              width: 2, height: 18, borderRadius: 1,
              background: qdbOnline ? 'var(--amber)' : 'rgba(255,255,255,0.1)',
            }}
              animate={qdbOnline ? { opacity: [0.3, 1, 0.3] } : {}}
              transition={{ duration: 0.8, delay: i * 0.15, repeat: Infinity }}
            />
          ))}
          <div style={{
            position: 'absolute',
            width: 0, height: 0,
            borderLeft: '5px solid transparent',
            borderRight: '5px solid transparent',
            borderTop: `7px solid ${qdbOnline ? 'var(--amber)' : 'rgba(255,255,255,0.1)'}`,
            transform: 'translateY(16px)',
          }} />
        </div>

        {/* Stage 2 → 3 → 4: Storage → Pipeline → Bus (horizontal grid) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr)', alignItems: 'center', gap: '0' }}>

          {/* STORAGE */}
          <motion.div
            animate={{ scale: qdbOnline ? 1.02 : 1 }}
            style={{
              flex: 1,
              padding: '14px 10px',
              borderRadius: '10px',
              border: `2px solid ${qdbOnline ? 'var(--amber)' : 'rgba(255,204,0,0.15)'}`,
              background: qdbOnline ? 'rgba(255,204,0,0.07)' : 'rgba(6,9,16,0.8)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
              boxShadow: qdbOnline ? '0 0 20px rgba(255,204,0,0.2)' : 'none',
              transition: 'all 0.4s',
              position: 'relative', overflow: 'hidden',
            }}>
            {qdbOnline && (
              <motion.div
                animate={{ x: ['-120%', '120%'] }}
                transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
                style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, transparent, rgba(255,204,0,0.1), transparent)', pointerEvents: 'none' }}
              />
            )}
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px' }}>🔥</div>
                <div style={{ fontSize: '0.58rem', fontWeight: 900, color: qdbOnline ? 'var(--amber)' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase' }}>QuestDB</div>
              </div>
              <div style={{ width: 1, height: 36, background: 'rgba(255,255,255,0.1)' }} />
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px' }}>💾</div>
                <div style={{ fontSize: '0.58rem', fontWeight: 900, color: qdbOnline ? 'var(--amber)' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase' }}>SQLite</div>
              </div>
            </div>
            <div style={{ fontSize: '0.55rem', fontWeight: 900, fontFamily: 'JetBrains Mono', color: qdbOnline ? '#fff' : 'var(--dim)', textTransform: 'uppercase' }}>
              {qdbOnline ? '⬤ WAL Writing' : '○ Offline'}
            </div>
            <div style={{ fontSize: '0.52rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>STORAGE LAYER</div>
          </motion.div>

          <PipelineArrow active={qdbOnline} color="var(--amber)" />

          {/* PIPELINE */}
          <motion.div
            animate={{ scale: pipeActive ? 1.02 : 1 }}
            style={{
              flex: 1,
              padding: '14px 10px',
              borderRadius: '10px',
              border: `2px solid ${pipeActive ? '#d4a5ff' : 'rgba(212,165,255,0.15)'}`,
              background: pipeActive ? 'rgba(212,165,255,0.07)' : 'rgba(6,9,16,0.8)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
              boxShadow: pipeActive ? '0 0 20px rgba(212,165,255,0.2)' : 'none',
              transition: 'all 0.4s',
              position: 'relative', overflow: 'hidden',
            }}>
            {pipeActive && (
              <motion.div
                animate={{ x: ['-120%', '120%'] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, transparent, rgba(212,165,255,0.12), transparent)', pointerEvents: 'none' }}
              />
            )}
            <span style={{ fontSize: '26px' }}>🔄</span>
            <div style={{ fontSize: '0.65rem', fontWeight: 900, color: pipeActive ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', textAlign: 'center' }}>
              Data Pipeline
            </div>
            <div style={{ fontSize: '0.55rem', fontWeight: 900, fontFamily: 'JetBrains Mono', color: pipeActive ? 'var(--violet)' : 'var(--dim)', textTransform: 'uppercase' }}>
              {pipeActive ? '⬤ PROCESSING' : '○ Awaiting'}
            </div>
            <div style={{ fontSize: '0.52rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>NORMALISE · ROUTE</div>
          </motion.div>

          <PipelineArrow active={brainOnline} color="var(--violet)" />

          {/* INTELLIGENCE BUS */}
          <motion.div
            animate={{ scale: brainOnline ? 1.02 : 1 }}
            style={{
              flex: 1,
              padding: '14px 10px',
              borderRadius: '10px',
              border: `2px solid ${brainOnline ? 'var(--cyan)' : 'rgba(0,229,255,0.15)'}`,
              background: brainOnline ? 'rgba(0,229,255,0.07)' : 'rgba(6,9,16,0.8)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
              boxShadow: brainOnline ? '0 0 20px rgba(0,229,255,0.2)' : 'none',
              transition: 'all 0.4s',
              position: 'relative', overflow: 'hidden',
            }}>
            {brainOnline && (
              <motion.div
                animate={{ x: ['-120%', '120%'] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
                style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, transparent, rgba(0,229,255,0.12), transparent)', pointerEvents: 'none' }}
              />
            )}
            <span style={{ fontSize: '26px' }}>⚡</span>
            <div style={{ fontSize: '0.55rem', fontWeight: 900, color: brainOnline ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase', textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Intelligence Bus
            </div>
            <div style={{ fontSize: '0.5rem', fontWeight: 900, fontFamily: 'JetBrains Mono', color: brainOnline ? 'var(--cyan)' : 'var(--dim)', textTransform: 'uppercase' }}>
              {brainOnline ? '⬤ LIVE' : '○ Standby'}
            </div>
            <div style={{ fontSize: '0.45rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono', letterSpacing: '0.01em' }}>Samvid v1.0-beta-beta-beta BUS</div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
