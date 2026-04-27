import React from 'react';

export const Label = ({ children, className = '' }) => (
  <span style={{ fontSize: '0.57rem', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}
    className={`c-dim ${className}`}>{children}</span>
);

export const Panel = ({ children, className = '', style = {} }) => (
  <div className={`glass-panel ${className}`} style={style}>{children}</div>
);

export const PanelHdr = ({ title, right, badge }) => (
  <div className="panel-hdr">
    <span className="panel-title">{title}</span>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {badge && <span className={`badge badge-${badge.color}`}>{badge.label}</span>}
      {right && <span style={{ fontSize: '0.57rem' }} className="c-dim font-mono">{right}</span>}
    </div>
  </div>
);

export const SecHdr = ({ title, right }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
    <Label className="c-muted">{title}</Label>
    {right && <span style={{ fontSize: '0.57rem' }} className="c-dim font-mono">{right}</span>}
  </div>
);

export const DataRow = ({ label, value, valueClass = '' }) => (
  <div className="data-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.55rem 0', gap: '0.8rem', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
    <span className="data-key" style={{ whiteSpace: 'nowrap', opacity: 0.6 }}>{label}</span>
    <span className={`data-val ${valueClass}`} style={{ textAlign: 'right', whiteSpace: 'nowrap', fontWeight: 900 }}>{value}</span>
  </div>
);

export const Sparkline = React.memo(({ data = [], color = '#00d4ff', h = 28, w = 72 }) => {
  const pts = React.useMemo(() => {
    if (!data || data.length < 2) return null;
    const vals = data.map(d => (typeof d === 'object' ? (d.close ?? d.price ?? 0) : d)).filter(v => typeof v === 'number' && isFinite(v));
    if (vals.length < 2) return null;
    const mn = Math.min(...vals), mx = Math.max(...vals);
    const range = mx - mn || 1;
    return vals.map((v, i) => {
      const x = (i / (vals.length - 1)) * w;
      const y = h - ((v - mn) / range) * (h - 4) - 2;
      return `${x},${y}`;
    }).join(' ');
  }, [data, h, w]);

  if (!pts) return <div style={{ width: w, height: h }} />;
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
});

export const ConnDot = ({ on }) => (
  <span className={`status-dot ${on ? 'c-cyan pulse' : 'c-red'}`}
    style={{ width: 7, height: 7, flexShrink: 0, boxShadow: on ? '0 0 8px var(--cyan)' : 'none' }} />
);

export const fmt = (n, dec = 2) => {
  const num = n === null || n === undefined || isNaN(Number(n)) ? 0 : Number(n);
  return num.toFixed(dec);
};

export const fmtMs = (s) => {
  s = Math.floor(s || 0);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s/60)}m ${s%60}s`;
  return `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m`;
};

// Pct bar
export const PctBar = ({ value, max = 100, color = 'var(--cyan)' }) => {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', width: '100%' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.4s ease' }} />
    </div>
  );
};
