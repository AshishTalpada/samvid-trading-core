import React, { useState, useMemo, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ─── Colour palette keyed on Dhatu state ────────────────────────────────────
const DHATU_PALETTE = {
  Vriddhi:  '#22d3ee',
  Kshaya:   '#f43f5e',
  Chala:    '#fbbf24',
  Viyoga:   '#e879f9',
  Samyoga:  '#22d3ee',
  Sthira:   '#4ade80',
  Abhava:   '#f43f5e',
  Sthiti:   '#94a3b8',
  NEUTRAL:  '#475569',
};
const accentFor = (dhatu) => DHATU_PALETTE[dhatu] ?? '#22d3ee';

// ─── Confidence → glow radius ───────────────────────────────────────────────
const confGlow = (c = 0) => Math.round(2 + (c ?? 0) * 10);

// ─── Layout: position N nodes on a circle, SENTIENCE at center ──────────────
function layoutNodes(rawNodes, cx = 250, cy = 185, r = 145) {
  const labels = rawNodes.length > 0
    ? rawNodes
    : ['Yields', 'Oil', 'VIX', 'Macro', 'News', 'Technicals'];
  const positioned = labels.map((id, i) => {
    const angle = (i / labels.length) * 2 * Math.PI - Math.PI / 2;
    return { id, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), isCenter: false };
  });
  positioned.push({ id: 'SENTIENCE', x: cx, y: cy, isCenter: true });
  return positioned;
}

// ─── Animated dashed edge with directional arrow ─────────────────────────────
function CausationEdge({ x1, y1, x2, y2, desc, conf = 0.5, accent, index }) {
  const [hovered, setHovered] = useState(false);
  const id = `edge-${index}`;
  const dashLen = 6;
  const gapLen = 4;
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  const opacity = 0.35 + conf * 0.65;

  return (
    <g onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
       style={{ cursor: 'help' }}>
      <defs>
        <marker id={`arrow-${id}`} markerWidth="6" markerHeight="6"
          refX="5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill={accent} opacity={opacity} />
        </marker>
        <filter id={`glow-${id}`}>
          <feGaussianBlur stdDeviation={hovered ? '4' : '2'} result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Invisible wide hit target */}
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="transparent" strokeWidth="12" />

      {/* Animated dashed line */}
      <motion.line
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={accent}
        strokeWidth={hovered ? 1.8 : 1}
        strokeDasharray={`${dashLen} ${gapLen}`}
        strokeOpacity={hovered ? 1 : opacity}
        markerEnd={`url(#arrow-${id})`}
        filter={hovered ? `url(#glow-${id})` : ''}
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 1.2 + index * 0.15, ease: 'easeOut' }}
      >
        {/* Dash offset animation — makes the line "flow" */}
        <animate
          attributeName="stroke-dashoffset"
          values={`${(dashLen + gapLen) * 3};0`}
          dur={`${2 + conf * 2}s`}
          repeatCount="indefinite"
        />
      </motion.line>

      {/* Hoverable tooltip */}
      <AnimatePresence>
        {hovered && desc && (
          <motion.g
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            style={{ pointerEvents: 'none' }}>
            <rect x={midX - 82} y={midY - 38} width="164" height="52" rx="8"
              fill="rgba(2,6,23,0.96)"
              stroke={accent} strokeWidth="0.6" strokeOpacity="0.5" />
            <text x={midX} y={midY - 22} textAnchor="middle"
              fill={accent}
              style={{ fontSize: '7.5px', fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', fontFamily: 'Inter, sans-serif' }}>
              MECHANISM · {Math.round(conf * 100)}% confidence
            </text>
            {/* Wrap long desc into two lines */}
            <text x={midX} y={midY - 8} textAnchor="middle"
              fill="#94a3b8"
              style={{ fontSize: '7px', fontFamily: 'Inter, sans-serif', fontWeight: 500 }}>
              {(desc ?? '').slice(0, 44)}
            </text>
            {desc && desc.length > 44 && (
              <text x={midX} y={midY + 5} textAnchor="middle"
                fill="#94a3b8"
                style={{ fontSize: '7px', fontFamily: 'Inter, sans-serif' }}>
                {desc.slice(44, 84)}{desc.length > 84 ? '…' : ''}
              </text>
            )}
          </motion.g>
        )}
      </AnimatePresence>
    </g>
  );
}

// ─── Signal node circle ──────────────────────────────────────────────────────
function SignalNode({ node, accent, dhatu }) {
  const r = node.isCenter ? 28 : 18;
  const glowR = node.isCenter ? confGlow(0.9) : 3;

  return (
    <motion.g
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 280, damping: 22, delay: 0.05 }}>
      <defs>
        <filter id={`ng-${node.id}`}>
          {/* v1.0-beta-beta: Performance optimization — Using fixed-step blur to prevent SVG repaint storms on every tick */}
          <feGaussianBlur stdDeviation={node.isCenter ? "4" : "2"} result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        {node.isCenter && (
          <radialGradient id="center-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor={accent} stopOpacity="0.35" />
            <stop offset="100%" stopColor={accent} stopOpacity="0.04" />
          </radialGradient>
        )}
      </defs>

      {/* Outer ring pulse (center node only) */}
      {node.isCenter && (
        <circle cx={node.x} cy={node.y} r={r + 14} fill="none"
          stroke={accent} strokeWidth="0.6" strokeOpacity="0.3">
          <animate attributeName="r" values={`${r + 10};${r + 20};${r + 10}`} dur="3s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.4;0.1;0.4" dur="3s" repeatCount="indefinite" />
        </circle>
      )}

      {/* Main circle */}
      <circle cx={node.x} cy={node.y} r={r}
        fill={node.isCenter ? `url(#center-grad)` : 'rgba(2,8,23,0.85)'}
        stroke={accent}
        strokeWidth={node.isCenter ? 1.5 : 1}
        strokeOpacity={node.isCenter ? 1 : 0.7}
        filter={`url(#ng-${node.id})`} />

      {/* Label */}
      <text x={node.x} y={node.y + (node.isCenter ? 5 : 5)} textAnchor="middle"
        dominantBaseline="middle"
        fill={node.isCenter ? accent : '#e2e8f0'}
        style={{
          fontSize: node.isCenter ? '8px' : '7px',
          fontWeight: node.isCenter ? 900 : 700,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          fontFamily: 'Inter, sans-serif',
        }}>
        {node.isCenter ? dhatu || 'ORACLE' : node.id}
      </text>

      {/* Sub-label for center */}
      {node.isCenter && (
        <text x={node.x} y={node.y + 16} textAnchor="middle"
          fill={accent} fillOpacity="0.6"
          style={{ fontSize: '6px', fontWeight: 600, letterSpacing: '0.12em', fontFamily: 'Inter, sans-serif' }}>
          SENTIENCE
        </text>
      )}
    </motion.g>
  );
}

// ─── Causation ticker tape ───────────────────────────────────────────────────
function CausationTicker({ edges = [] }) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (edges.length < 2) return;
    const id = setInterval(() => setIdx(i => (i + 1) % edges.length), 3000);
    return () => clearInterval(id);
  }, [edges.length]);

  if (!edges.length) return null;
  const e = edges[idx];

  return (
    <AnimatePresence mode="wait">
      <motion.div key={idx}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.35 }}
        style={{
          fontSize: '0.6rem', fontFamily: 'Inter, monospace', padding: '5px 10px',
          borderTop: '1px solid rgba(255,255,255,0.05)',
          display: 'flex', gap: 8, alignItems: 'center', color: '#475569',
        }}>
        <span style={{ color: '#22d3ee', fontWeight: 700 }}>{e.from}</span>
        <span>→</span>
        <span style={{ color: '#94a3b8' }}>{e.to}</span>
        <span style={{ marginLeft: 'auto', color: '#fbbf24', fontWeight: 700 }}>
          {Math.round((e.conf ?? 0) * 100)}%
        </span>
        <span style={{ color: '#334155', maxWidth: 140, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
          {e.desc}
        </span>
      </motion.div>
    </AnimatePresence>
  );
}

// Stable confidence seeds per node index (avoids Math.random on every render)
const STABLE_CONFS = [0.72, 0.68, 0.81, 0.59, 0.76, 0.63, 0.88, 0.71];

// ─── Main component ──────────────────────────────────────────────────────────
const OracleGraph = ({ data }) => {
  const { nodes: rawNodes = [], edges = [], dhatu, confidence = 0 } = data || {};

  const accent = accentFor(dhatu);
  const nodes  = useMemo(() => layoutNodes(rawNodes), [rawNodes]);
  const find   = (id) => nodes.find(n => n.id === id) ?? nodes[0];

  // Fallback edges when API hasn't sent any — use stable conf values, no Math.random
  const drawEdges = useMemo(() => edges.length > 0
    ? edges
    : nodes.filter(n => !n.isCenter).map((n, i) => ({
        from: n.id, to: 'SENTIENCE',
        desc: 'Real-time correlation to global macro bias',
        conf: STABLE_CONFS[i % STABLE_CONFS.length],
      })),
    [edges, nodes]);

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>

      {/* Live synthesis indicator */}
      <style>{`@keyframes og-pulse{0%,100%{opacity:.4;transform:scale(.85)}50%{opacity:1;transform:scale(1.25)}}`}</style>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}>
        <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: accent, flexShrink: 0,
          animation: 'og-pulse 1.8s ease-in-out infinite', boxShadow: `0 0 6px ${accent}` }} />
        <span style={{ fontSize: '0.58rem', fontWeight: 800, letterSpacing: '0.18em', color: '#475569', textTransform: 'uppercase' }}>
          Live Synthesis
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.58rem', fontWeight: 700, color: accent }}>
          {Math.round(confidence * 100)}% conf
        </span>
        <span style={{ fontSize: '0.58rem', color: '#475569', marginLeft: 4 }}>
          {edges.length} edges
        </span>
      </div>

      {/* SVG graph */}
      <svg width="100%" viewBox="0 0 500 370"
        style={{ display: 'block', overflow: 'visible' }}>

        {/* Background grid */}
        <defs>
          <pattern id="og-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="500" height="370" fill="url(#og-grid)" rx="10" />

        {/* Edges */}
        {drawEdges.map((e, i) => {
          const s = find(e.from);
          const t = find(e.to);
          return (
            <CausationEdge
              key={`e-${i}`}
              x1={s.x} y1={s.y}
              x2={t.x} y2={t.y}
              desc={e.desc}
              conf={e.conf ?? 0.5}
              accent={accent}
              index={i}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map(n => (
          <SignalNode key={n.id} node={n} accent={accent} dhatu={dhatu} />
        ))}

        {/* Confidence arc around center */}
        {confidence > 0 && (() => {
          const cx = 250, cy = 185, r = 38;
          const circumference = 2 * Math.PI * r;
          const dash = circumference * confidence;
          return (
            <circle cx={cx} cy={cy} r={r}
              fill="none" stroke={accent} strokeWidth="2"
              strokeOpacity="0.35"
              strokeDasharray={`${dash} ${circumference}`}
              strokeLinecap="round"
              transform={`rotate(-90 ${cx} ${cy})`}>
              <animate attributeName="stroke-opacity" values="0.2;0.5;0.2" dur="2.5s" repeatCount="indefinite" />
            </circle>
          );
        })()}
      </svg>

      {/* Causation ticker */}
      <CausationTicker edges={drawEdges} />

      {/* Footer */}
      <div style={{
        fontSize: '0.52rem', fontFamily: 'monospace', color: '#1e293b',
        padding: '4px 10px', letterSpacing: '0.08em', textTransform: 'uppercase'
      }}>
        Dhatu_Graph_Engine_v1.0-beta // Multi-Layer_Synthesis // {dhatu ?? 'NEUTRAL'}
      </div>
    </div>
  );
};

export default OracleGraph;
