import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';

/** 🪐 SOVEREIGN NEURAL TOPOLOGY V4.0 | LIVE AGENT REAL-TIME COMPONENT 🪐
 *  A unified observatory grid visualizing all core backend cognitive layers.
 */

const NODE_H = 70, NODE_W = 130;
const BUS_W  = 1200, BUS_H = 80;
const VB_W   = 1600, VB_H  = 1000;

const LAYER_CFG = [
  { id: 'sources',   y: 80,   color: '#818cf8', label: 'MARKET DATA SOURCES' },
  { id: 'storage',   y: 220,  color: '#fbbf24', label: 'DISTRIBUTED CACHE' },
  { id: 'pipelines', y: 360,  color: '#c084fc', label: 'COLD/HOT INGESTION' },
  { id: 'bus',       y: 500,  color: '#ffffff', label: 'INTELLIGENCE BUS' },
  { id: 'agents',    y: 680,  color: '#00ffaa', label: 'AUTONOMOUS AGENTS' },
  { id: 'minds',     y: 820,  color: '#d4a5ff', label: 'COGNITIVE MINDS' },
  { id: 'inference', y: 960,  color: '#fbbf24', label: 'DECISION OVERLAY' },
];

function Edge({ from, to, active, dashed, color, i, lastAct, pulseCount }) {
  if (from?.x === undefined || from?.y === undefined || to?.x === undefined || to?.y === undefined) return null;
  const path = `M ${from.x} ${from.y} L ${to.x} ${to.y}`;
  return (
    <g>
      <path d={path}
        stroke={active ? color : `${color}30`}
        strokeWidth={active ? 2.5 : 1.2}
        fill="none"
        strokeDasharray={dashed ? '5 6' : 'none'}
        opacity={active ? 0.9 : 0.4}
        style={{ transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)' }}
      />
      {active && (
        <motion.circle r={3.5} fill={color}
          style={{ offsetPath: `path('${path}')`, filter: `drop-shadow(0 0 5px ${color})` }}
          initial={{ opacity: 0, offsetDistance: '0%' }}
          animate={{ offsetDistance: '100%', opacity: [0, 1, 0] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'linear', delay: i * 0.08 }}
        />
      )}
      {/* ⚡ HFT Burst Packet */}
      {pulseCount > 0 && (
        <motion.circle key={pulseCount} r={4.5} fill="#fff"
          style={{ offsetPath: `path('${path}')`, filter: `drop-shadow(0 0 8px #fff)` }}
          initial={{ opacity: 0, offsetDistance: '0%' }}
          animate={{ offsetDistance: '100%', opacity: [0, 1, 0] }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
        />
      )}
    </g>
  );
}

function Node({ node, active, offline, status, pulseCount }) {
  if (node?.x === undefined || node?.y === undefined) return null;
  const col = offline ? '#ff3366' : node.color;
  const w = NODE_W, h = NODE_H;
  
  return (
    <motion.g transform={`translate(${node.x},${node.y})`}
      animate={{ scale: active ? 1.08 : 1 }}>
      {/* HFT Pulse Flash */}
      <motion.rect key={pulseCount} x={-w/2} y={-h/2} width={w} height={h} rx={8}
        fill="#fff" opacity={0}
        animate={{ opacity: [0, 0.4, 0] }}
        transition={{ duration: 0.1 }}
      />
      {/* Pulse / Activity Glow */}
      {active && !offline && (
        <motion.rect x={-w/2-5} y={-h/2-5} width={w+10} height={h+10} rx={12}
          fill="none" stroke={col} strokeWidth={1}
          animate={{ opacity: [0.6, 0.1, 0.6], scale: [0.98, 1.12, 0.98] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
      )}
      {/* Body */}
      <rect x={-w/2} y={-h/2} width={w} height={h} rx={8}
        fill={offline ? 'rgba(255,51,102,0.12)' : active ? `${col}15` : 'rgba(3,5,10,0.92)'}
        stroke={offline ? '#ff3366' : active ? col : 'rgba(255,255,255,0.12)'}
        strokeWidth={active ? 2 : 1}
        style={{ filter: active && !offline ? `drop-shadow(0 0 12px ${col}50)` : 'none', transition: 'all 0.4s' }}
      />
      {/* Content */}
      <text x={-w/2 + 24} textAnchor="middle" dominantBaseline="middle" style={{ fontSize: '24px' }}>
        {offline ? '🛑' : node.icon}
      </text>
      <text x={18} y={-10} dominantBaseline="middle"
        fill={active ? '#fff' : 'rgba(255,255,255,0.7)'}
        style={{ fontSize: '22px', fontWeight: 900, fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '1px' }}>
        {node.label}
      </text>
      <text x={18} y={16} dominantBaseline="middle"
        fill={active ? col : 'rgba(255,255,255,0.3)'}
        style={{ fontSize: '16px', fontWeight: 800, fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>
        {status || (offline ? 'DISCONNECTED' : active ? 'FLOWING' : 'IDLE')}
      </text>
    </motion.g>
  );
}

function IntelligenceBusNode({ node, active, pulseCount }) {
  return (
    <motion.g transform={`translate(${node.x},${node.y})`} animate={{ scale: active ? 1.02 : 1 }}>
      <rect x={-BUS_W/2} y={-BUS_H/2} width={BUS_W} height={BUS_H} rx={10}
        fill={active ? 'rgba(255,255,255,0.06)' : 'rgba(2,4,8,0.98)'}
        stroke={active ? '#ffffff' : 'rgba(255,255,255,0.15)'}
        strokeWidth={active ? 3 : 1.5}
        style={{ filter: active ? 'drop-shadow(0 0 15px rgba(255,255,255,0.2))' : 'none', transition: 'box-shadow 0.4s' }}
      />
      <text x={0} dominantBaseline="middle" textAnchor="middle"
        fill={active ? '#fff' : 'rgba(255,255,255,0.45)'}
        style={{ fontSize: '34px', fontWeight: 900, fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '4px' }}>
        ⚡ {node.label}
      </text>
      {active && (
        <motion.rect x={-BUS_W/2} y={-BUS_H/2} width={BUS_W} height={BUS_H} rx={10}
          fill="none" stroke="#fff" strokeWidth={1}
          animate={{ opacity: [0.1, 0.4, 0.1], scaleX: [1, 1.005, 1], scaleY: [1, 1.05, 1] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />
      )}
    </motion.g>
  );
}

export default function SystemFlowchart({ brain = {}, health = {}, activityMap = {}, pulseMap = {}, eventQueue = [] }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    let frame;
    const loop = () => {
      setNow(Date.now());
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, []);

  const agents = useMemo(() => brain?.agents ?? {}, [brain]);
  const minds  = useMemo(() => brain?.minds ?? {}, [brain]);
  const activeCount = useMemo(() => Object.values(activityMap).filter(t => (now - t) < 3000).length, [activityMap, now]);
  
  const isAct = (id) => (now - (activityMap[id] || 0)) < 3000;
  const getStatus = (id) => {
    if (id.startsWith('agent_')) return agents[id]?.status;
    if (id.startsWith('mind_')) return minds[id.replace('mind_','')]?.status;
    return null;
  };

  const isOffline = (id) => {
    const c = health?.components || {};
    const m = {
      ibkr:      c.ibkr      ?? c.IBKR,
      questdb:   c.questdb   ?? c.qdb  ?? c.QDB,
      sqlite:    c.sqlite    ?? c.qdb  ?? c.QDB,
      intel_bus: c.intel_bus ?? c.brain ?? c.seto,
      oracle:    c.oracle    ?? c.dhatu ?? c.DHATU,
    };
    return m[id] === 'OFFLINE';
  };

  // Define Layout Nodes
  const nodes = useMemo(() => {
    const row = (defs, ly, tw) => {
      const gap = tw / (defs.length + 1);
      return defs.map((d, i) => ({ ...d, x: Math.round(gap * (i + 1)), y: ly }));
    };

    const sourceNodes  = row([
      { id: 'ibkr',     label: 'IBKR',     icon: '⚡', color: '#00e5ff' },
      { id: 'yfinance', label: 'YFIN',     icon: '📊', color: '#8899ac' },
      { id: 'openbb',   label: 'OBB',      icon: '🌐', color: '#d4a5ff' },
      { id: 'finnhub',  label: 'FINN',     icon: '📰', color: '#ffcc00' },
      { id: 'archive',  label: 'ARCHIVE',  icon: '🛰️', color: '#00e5ff' },
    ], LAYER_CFG[0].y, VB_W);

    const storageNodes = row([
      { id: 'questdb', label: 'QUESTDB', icon: '🔥', color: '#ffcc00' },
      { id: 'sqlite',  label: 'SQLITE',  icon: '💾', color: '#ffcc00' },
    ], LAYER_CFG[1].y, VB_W);

    const pipNode    = [{ id: 'pipeline', label: 'DATA PIPELINE', icon: '🔄', color: '#d4a5ff', x: VB_W / 2, y: LAYER_CFG[2].y }];
    const busNode    = [{ id: 'intel_bus', label: 'INTELLIGENCE BUS · SETO V8.5', icon: '⚡', color: '#ffffff', x: VB_W / 2, y: LAYER_CFG[3].y, isCore: true }];
    
    const agKeys = Object.keys(agents).sort();
    const agNodes = row(agKeys.length > 0
      ? agKeys.map(k => {
          let lbl = k.replace('agent_', '').toUpperCase();
          if (lbl === 'RISK_GUARD') lbl = 'RISK';
          if (lbl === 'DHATU_ORACLE') lbl = 'DHATU';
          if (lbl === 'SWARM_PREDICTOR') lbl = 'SWARM';
          if (lbl === 'MIND_ULTRATHINK') lbl = 'ULTRA';
          return { id: k, label: lbl, icon: '🤖', color: '#00ffaa' };
        })
      : ['agent_a','agent_b','agent_c','agent_d','agent_e','agent_f','agent_g','risk_guard','dhatu_oracle','swarm_predictor','mind_ultrathink'].map(id => {
          let lbl = id.replace('agent_', '').toUpperCase();
          if (lbl === 'RISK_GUARD') lbl = 'RISK';
          if (lbl === 'DHATU_ORACLE') lbl = 'DHATU';
          if (lbl === 'SWARM_PREDICTOR') lbl = 'SWARM';
          if (lbl === 'MIND_ULTRATHINK') lbl = 'ULTRA';
          return { id, label: lbl.slice(0,5), icon: '🤖', color: '#00ffaa' };
        }),
      LAYER_CFG[4].y, VB_W
    );

    const mKeys = Object.keys(minds).sort();
    const mnNodes = row(mKeys.length > 0
      ? mKeys.map(m => ({ id: `mind_${m}`, label: m.toUpperCase(), icon: '🧬', color: '#d4a5ff' }))
      : ['ARCH','EVO','OBS','EXP','ULTRA','SYS','GHOST'].map(l => ({ id: `mind_${l.toLowerCase()}`, label: l, icon: '🧬', color: '#d4a5ff' })),
      LAYER_CFG[5].y, VB_W
    );

    const intNodes = row([
      { id: 'oracle',    label: 'ORACLE',    icon: '🔮', color: '#d4a5ff' },
      { id: 'swarm',     label: 'SWARM',     icon: '🐝', color: '#00ffaa' },
      { id: 'consensus', label: 'CONSENSUS', icon: '⚖️', color: '#00ffaa' },
      { id: 'exit_iq',   label: 'EXIT IQ',   icon: '🎯', color: '#ffcc00' },
      { id: 'dms_guard', label: 'DMS',       icon: '🛡️', color: '#ffffff' },
    ], LAYER_CFG[6].y, VB_W);

    const allNodes = [...sourceNodes, ...storageNodes, ...pipNode, ...busNode, ...agNodes, ...mnNodes, ...intNodes];
    // Deduplicate by ID to prevent React key crashes
    const unique = [];
    const seen = new Set();
    for (const n of allNodes) {
      if (!seen.has(n.id)) {
        unique.push(n);
        seen.add(n.id);
      }
    }
    return unique;
  }, [agents, minds]);

  const find = (id) => nodes.find(n => n.id === id);
  const edges = useMemo(() => [
    { from: 'ibkr', to: 'questdb' }, { from: 'yfinance', to: 'questdb' },
    { from: 'openbb', to: 'sqlite' }, { from: 'finnhub', to: 'sqlite' }, { from: 'archive', to: 'sqlite' },
    { from: 'questdb', to: 'pipeline' }, { from: 'sqlite', to: 'pipeline' },
    { from: 'pipeline', to: 'intel_bus' },
    ...nodes.filter(n => n.id.startsWith('agent_')).map(n => ({ from: 'intel_bus', to: n.id })),
    ...nodes.filter(n => n.id.startsWith('agent_')).map(n => ({ from: n.id, to: 'consensus', dashed: true })),
    ...nodes.filter(n => n.id.startsWith('mind_')).map(n => ({ from: 'intel_bus', to: n.id, dashed: true })),
    { from: 'intel_bus', to: 'oracle' }, { from: 'oracle', to: 'swarm' }, { from: 'swarm', to: 'consensus' },
    { from: 'consensus', to: 'exit_iq' }, { from: 'exit_iq', to: 'dms_guard' },
  ].map(e => ({ ...e, F: find(e.from), T: find(e.to) })).filter(e => e.F && e.T), [nodes]);

  const latestCon = eventQueue.find(e => e.type === 'consensus.update');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%', background: 'rgba(2,5,10,0.4)' }}>
      {/* Dynamic Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)' }}>
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
            🛸 Neural Topology Mirror <span style={{ color: 'var(--cyan)', opacity: 0.8 }}>V4.0 LIVE</span>
          </div>
          {latestCon && (now - (latestCon.timestamp || 0) < 5000) && (
            <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
              style={{ fontSize: '0.65rem', color: 'var(--emerald)', fontWeight: 800, fontFamily: 'JetBrains Mono', marginTop: 3 }}>
              ⚖️ CONSENSUS: {latestCon.data?.phase} / [{latestCon.data?.symbol}] • {latestCon.data?.decision}
            </motion.div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '25px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase' }}>Mesh Density</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: 'var(--cyan)', fontFamily: 'JetBrains Mono' }}>{activeCount} <span style={{fontSize: '0.7rem'}}>ACT</span></div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase' }}>Bus Logic</div>
            <div style={{ fontSize: '0.8rem', fontWeight: 900, color: isAct('intel_bus') ? 'var(--emerald)' : '#ff3366', fontFamily: 'JetBrains Mono' }}>
              {isAct('intel_bus') ? 'SYNCED' : 'AWAITING'}
            </div>
          </div>
        </div>
      </div>

      <svg viewBox={`0 0 ${VB_W} ${VB_H}`} style={{ flex: 1, display: 'block', padding: '20px', maxHeight: '100%' }}>
        {/* Topology Bands */}
        {LAYER_CFG.map(lyr => (
          <g key={lyr.id}>
            <line x1="0" y1={lyr.y - 65} x2={VB_W} y2={lyr.y - 65} stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            <text x="8" y={lyr.y - 45} fill={lyr.color} opacity="0.6" style={{ fontSize: '20px', fontWeight: 900, fontFamily: 'JetBrains Mono', letterSpacing: '2px' }}>
              {lyr.label}
            </text>
          </g>
        ))}

        {/* Live Links */}
        {edges.map((e, i) => (
          <Edge key={`${e.from}-${e.to}`}
            from={e.F} to={e.T} active={isAct(e.from) || isAct(e.to)} 
            lastAct={Math.max(activityMap[e.from] || 0, activityMap[e.to] || 0)}
            pulseCount={(pulseMap[e.from] || 0) + (pulseMap[e.to] || 0)}
            dashed={e.dashed} color={e.F.color} i={i} />
        ))}

        {/* Active Nodes */}
        {nodes.map(n => n.isCore ? (
          <IntelligenceBusNode key={n.id} node={n} active={isAct(n.id)} pulseCount={pulseMap[n.id] || 0} />
        ) : (
          <Node key={n.id} node={n} active={isAct(n.id)} offline={isOffline(n.id)} status={getStatus(n.id)} pulseCount={pulseMap[n.id] || 0} />
        ))}
      </svg>
    </div>
  );
}
