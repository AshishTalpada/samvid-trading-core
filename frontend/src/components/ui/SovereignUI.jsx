import React from 'react';
import { motion } from 'framer-motion';

/** 🧩 Standard UI Design System Components (SETO V13.6.4 - Institutional Grade) */

export function GlassPanel({ children, className = '', depth = 'base', style = {} }) {
  const depthClass = depth === 'hi' ? 'glass-panel-hi' : '';
  return (
    <div className={`glass-panel ${depthClass} ${className}`} style={style}>
      {children}
    </div>
  );
}

export function SectionHeader({ title, icon, right, sub }) {
  return (
    <div className="section-header" style={{ borderLeft: '3px solid rgba(255,255,255,0.05)', background: 'linear-gradient(90deg, rgba(255,255,255,0.02), transparent)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {icon && <span style={{ fontSize: '14px', filter: 'drop-shadow(0 0 5px currentColor)' }}>{icon}</span>}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span className="fw-900 c-top ls-wider uppercase" style={{ fontSize: '0.65rem', letterSpacing: '0.15em' }}>{title}</span>
          {sub && <span className="fw-700 c-dim uppercase" style={{ fontSize: '0.55rem', opacity: 0.6 }}>{sub}</span>}
        </div>
      </div>
      {right && <div style={{ fontSize: '0.6rem' }} className="font-mono c-mid">{right}</div>}
    </div>
  );
}

export function StatCard({ label, value, subValue, trend, color = 'cyan' }) {
  return (
    <motion.div whileHover={{ scale: 1.02 }} transition={{ type: 'spring', stiffness: 400, damping: 10 }}>
      <GlassPanel className="stat-card" style={{ boxShadow: `inset 0 0 20px rgba(0,0,0,0.2)` }}>
        <span className="fw-800 c-dim uppercase ls-wider" style={{ fontSize: '0.5rem' }}>{label}</span>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className={`fw-900 font-outfit c-${color}`} style={{ fontSize: '1.5rem', textShadow: `0 0 10px var(--${color})44` }}>{value}</span>
          {trend !== undefined && (
            <span className={`fw-800 ${trend >= 0 ? "c-emerald" : "c-red"}`} style={{ fontSize: '0.65rem', background: trend >= 0 ? 'rgba(0,255,170,0.05)' : 'rgba(255,51,102,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
              {trend >= 0 ? '▲' : '▼'} {Math.abs(trend)}%
            </span>
          )}
        </div>
        {subValue && <span className="font-mono" style={{ fontSize: '0.55rem', color: 'rgba(255,255,255,0.3)' }}>{subValue}</span>}
      </GlassPanel>
    </motion.div>
  );
}

export function DataRow({ label, value, color = 'top', className = '' }) {
  return (
    <div className={`data-row ${className}`} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', padding: '0.55rem 0' }}>
      <span className="fw-800 c-dim uppercase" style={{ fontSize: '0.55rem', letterSpacing: '0.05em' }}>{label}</span>
      <span className={`font-mono fw-800 c-${color}`} style={{ fontSize: '0.6rem' }}>{value}</span>
    </div>
  );
}

export function Divider({ className = '' }) {
  return <div style={{ height: '1px', width: '100%', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent)', margin: '12px 0' }} className={className} />;
}

export function StatusBadge({ label, status = 'nominal', color = 'cyan' }) {
  const isPulse = status === 'nominal' || status === 'active';
  return (
    <div style={{ 
        display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 10px', 
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px' 
      }}>
      <div className={isPulse ? "pulse" : ""} style={{ 
          width: '5px', height: '5px', borderRadius: '50%', backgroundColor: `var(--${color})`,
          boxShadow: `0 0 10px var(--${color})`
        }} />
      <span className="fw-900 c-top ls-wider uppercase" style={{ fontSize: '0.5rem' }}>{label}</span>
    </div>
  );
}
