import React from 'react';
import { motion } from 'framer-motion';

const DHATU_COLORS = {
  Vriddhi: { text: 'var(--cyan)', bg: 'rgba(0,229,255,0.12)', border: 'rgba(0,229,255,0.4)' },
  Kshaya: { text: 'var(--red)', bg: 'rgba(255,51,102,0.12)', border: 'rgba(255,51,102,0.4)' },
  Chala: { text: 'var(--amber)', bg: 'rgba(255,204,0,0.12)', border: 'rgba(255,204,0,0.4)' },
  Viyoga: { text: 'var(--violet)', bg: 'rgba(212,165,255,0.12)', border: 'rgba(212,165,255,0.4)' },
  Samyoga: { text: 'var(--cyan)', bg: 'rgba(0,229,255,0.12)', border: 'rgba(0,229,255,0.4)' },
  Sthira: { text: 'var(--emerald)', bg: 'rgba(0,255,170,0.10)', border: 'rgba(0,255,170,0.35)' },
  Abhava: { text: 'var(--red)', bg: 'rgba(255,51,102,0.12)', border: 'rgba(255,51,102,0.4)' },
  Sthiti: { text: 'var(--mid)', bg: 'rgba(168,184,204,0.08)', border: 'rgba(168,184,204,0.2)' },
  NEUTRAL: { text: 'var(--mid)', bg: 'rgba(168,184,204,0.08)', border: 'rgba(168,184,204,0.2)' },
};

const dCol = (s) => DHATU_COLORS[s] ?? DHATU_COLORS.NEUTRAL;

export default function DhatuStateRing({ oracle }) {
  const dc = dCol(oracle?.dhatu);
  const dhatu = oracle?.dhatu ?? '---';
  const bias = oracle?.bias ?? 'NEUTRAL';
  const conf = ((oracle?.confidence ?? 0) * 100).toFixed(0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1rem 0 0.75rem', position: 'relative' }}>
      {/* Outer pulse ring */}
      <motion.div
        initial={{ scale: 1, opacity: 0.3 }}
        animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.6, 0.3] }}
        transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
        style={{
          position: 'absolute', top: '0.9rem',
          width: 100, height: 100,
          borderRadius: '50%',
          border: `1px solid ${dc.border}`,
          pointerEvents: 'none',
        }}
      />

      {/* Target ring */}
      <motion.div
        key={dhatu}
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, type: 'spring' }}
        style={{
          width: 90, height: 90, borderRadius: '50%',
          border: `2px solid ${dc.border}`,
          boxShadow: `0 0 30px ${dc.border}, inset 0 0 30px ${dc.bg}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: dc.bg, marginBottom: 12,
        }}
      >
        <span style={{ color: dc.text, fontSize: '0.65rem', fontWeight: 900, letterSpacing: '0.12em', textAlign: 'center', padding: '0 6px', fontFamily: 'Outfit, sans-serif' }}>
          {dhatu}
        </span>
      </motion.div>

      {/* Large dhatu label */}
      <div style={{ color: dc.text, fontSize: '1.35rem', fontWeight: 900, letterSpacing: '-0.02em', fontFamily: 'Outfit, sans-serif', textAlign: 'center' }}>
        {dhatu}
      </div>

      {/* Macro bias */}
      <div style={{ fontSize: '0.62rem', marginTop: 4, letterSpacing: '0.1em', color: 'var(--dim)', textAlign: 'center' }}>
        Macro Bias: <span style={{ color: dc.text }}>{bias}</span>
      </div>

      {/* Confidence */}
      <div style={{ fontSize: '0.62rem', marginTop: 2, textAlign: 'center', color: 'var(--dim)' }}>
        Confidence: <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{conf}%</span>
      </div>
    </div>
  );
}
