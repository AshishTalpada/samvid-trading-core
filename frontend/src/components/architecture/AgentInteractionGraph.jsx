import React, { useMemo, useState, useEffect } from 'react';
import { motion } from 'framer-motion';

/** 🤖 MULTI-AGENT NETWORK V4.0 | LIVE OBSERVATORY COMPONENT 🤖
 *  A high-fidelity mesh visualizing agent cross-talk and consensus logic.
 */

const AGENT_COLORS = { 
  agent_a: '#00e5ff', 
  agent_b: '#d4a5ff', 
  agent_c: '#ffcc00', 
  agent_d: '#00ffaa', 
  agent_e: '#ff3366', 
  agent_f: '#ff9900', 
  agent_g: '#ffffff',
  risk_guard: '#ff0000',
  dhatu_oracle: '#9d00ff',
  swarm_predictor: '#00ffcc',
  mind_ultrathink: '#ff00ff'
};

const AGENT_ROLES = { 
  agent_a: 'Gatekeeper', 
  agent_b: 'Classifier', 
  agent_c: 'Executor', 
  agent_d: 'Optimizer', 
  agent_e: 'Sentinel',
  agent_f: 'Oracle',
  agent_g: 'Architect',
  risk_guard: 'Safety',
  dhatu_oracle: 'Macro',
  swarm_predictor: 'Swarm',
  mind_ultrathink: 'Cortex'
};

const HUB_CX = 270, HUB_CY = 185;

function MeshEdge({ from, to, active, color, pulseCount }) {
  if (from?.cx === undefined || from?.cy === undefined || to?.x === undefined || to?.y === undefined) return null;
  const path = `M ${from.cx} ${from.cy} L ${to.x} ${to.y}`;
  return (
    <g>
      <path d={path} stroke={active ? color : 'rgba(255,255,255,0.05)'}
        strokeWidth={active ? 2.5 : 1} fill="none"
        opacity={active ? 0.9 : 0.25}
        style={{ transition: 'all 0.6s ease' }}
      />
      {active && (
        <motion.circle r={5} fill={color}
          style={{ offsetPath: `path('${path}')`, filter: `drop-shadow(0 0 8px ${color})` }}
          initial={{ opacity: 0, offsetDistance: '0%' }}
          animate={{ offsetDistance: '100%', opacity: [0, 1, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
        />
      )}
      {/* ⚡ HFT Burst Packet */}
      {pulseCount > 0 && (
        <motion.circle key={pulseCount} r={6} fill="#fff"
          style={{ offsetPath: `path('${path}')`, filter: `drop-shadow(0 0 10px #fff)` }}
          initial={{ opacity: 0, offsetDistance: '0%' }}
          animate={{ offsetDistance: '100%', opacity: [0, 1, 0] }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
        />
      )}
    </g>
  );
}

function AgentNode({ agent, active, pulseCount }) {
  if (agent?.cx === undefined || agent?.cy === undefined) return null;
  const r = 30;
  return (
    <motion.g transform={`translate(${agent.cx},${agent.cy})`} animate={{ scale: active ? 1.1 : 1 }}>
      {/* HFT Pulse Flash */}
      <motion.circle key={pulseCount} r={30} fill="#fff" opacity={0}
        animate={{ opacity: [0, 0.4, 0] }}
        transition={{ duration: 0.2 }}
      />
      <motion.circle r={r} fill="rgba(6,10,18,0.95)"
        stroke={active ? agent.color : 'rgba(255,255,255,0.12)'}
        strokeWidth={active ? 3 : 1.5}
        style={{ filter: active ? `drop-shadow(0 0 16px ${agent.color}80)` : 'none', transition: 'all 0.4s' }}
      />
      <text y={-(r + 15)} textAnchor="middle" fill={active ? '#fff' : 'rgba(255,255,255,0.45)'}
        style={{ fontSize: '12px', fontWeight: 900, fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '1px' }}>
        {agent.id.replace('agent_', '').replace('Agent_', '').replace('Mind_', '').toUpperCase()}
      </text>
      <text y={r + 18} textAnchor="middle" fill={active ? agent.color : 'rgba(255,255,255,0.25)'}
        style={{ fontSize: '9px', fontWeight: 800, fontFamily: 'JetBrains Mono' }}>
        {agent.role}
      </text>
      <text dominantBaseline="middle" textAnchor="middle" style={{ fontSize: '16px' }}>🤖</text>
      {active && (
        <motion.circle r={r + 6} fill="none" stroke={agent.color} strokeWidth={1}
          animate={{ r: [r+6, r+14, r+6], opacity: [0.4, 0, 0.4] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}
    </motion.g>
  );
}

export default function AgentInteractionGraph({ brain = {}, eventQueue = [], activityMap = {}, pulseMap = {} }) {
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

  const rawAgents = useMemo(() => {
    const systemAgents = brain?.agents || {};
    if (Object.keys(systemAgents).length > 0) return systemAgents;
    return { 
        agent_a: { status: 'STANDBY' }, 
        agent_b: { status: 'STANDBY' }, 
        agent_c: { status: 'STANDBY' }, 
        agent_d: { status: 'STANDBY' } 
    };
  }, [brain]);

  const agentList = useMemo(() => {
    const entries = Object.entries(rawAgents);
    return entries.map(([id, data], i) => {
      // V3.1: Division-by-zero guard
      const len = entries.length || 1; 
      const angle = (i / len) * 2 * Math.PI - Math.PI / 2;
      const R = 135;
      return {
        id,
        cx: HUB_CX + R * Math.cos(angle),
        cy: HUB_CY + R * Math.sin(angle),
        color: AGENT_COLORS[id] || '#8899ac',
        role: data.role || AGENT_ROLES[id] || 'Processor',
        status: data.status || 'ACTIVE',
        lastAct: activityMap[id] || 0,
      };
    });
  }, [rawAgents, activityMap]);

  const lastCon = eventQueue.find(e => e.type === 'consensus.update')?.timestamp || activityMap['consensus'] || 0;
  const hubActive = (now - lastCon) < 3000;
  const phase = eventQueue.findLast(e => e.type === 'consensus.update')?.data?.phase || 'SYNCHRONIZED';
  const pktCount = useMemo(() => Object.values(activityMap).filter(t => (now - t) < 3000).length, [activityMap, now]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '15px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '18px' }}>🤖</span>
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
              Multi-Agent Mesh <span style={{ color: 'var(--cyan)' }}>V4.0 LIVE</span>
            </div>
            <div style={{ fontSize: '0.6rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              {agentList.length} NEURAL TERMINALS ONLINE
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '25px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase' }}>Cross-Talk</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: 'var(--cyan)', fontFamily: 'JetBrains Mono' }}>{pktCount}/s</div>
          </div>
          <div style={{ textAlign: 'right' }}>
             <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase' }}>Hub Status</div>
             <div style={{ fontSize: '0.8rem', fontWeight: 900, color: hubActive ? 'var(--emerald)' : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
               {hubActive ? 'STREAMING' : 'IDLE'}
             </div>
          </div>
        </div>
      </div>

      <svg viewBox="0 0 540 380" style={{ flex: 1, display: 'block', background: 'rgba(2,4,8,0.5)' }}>
        <defs>
          <radialGradient id="hub-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(212,165,255,0.25)" />
            <stop offset="100%" stopColor="rgba(212,165,255,0)" />
          </radialGradient>
        </defs>

        <circle cx={HUB_CX} cy={HUB_CY} r={160} fill="url(#hub-glow)" />
        {[70, 135, 170].map(r => (
            <circle key={r} cx={HUB_CX} cy={HUB_CY} r={r} fill="none" stroke="rgba(255,255,255,0.04)" strokeDasharray="5 10" />
        ))}

        {/* Live Edges */}
        {agentList.map(a => (
          <MeshEdge key={a.id} from={a} to={{ x: HUB_CX, y: HUB_CY }} 
            active={(now - a.lastAct) < 3000} color={a.color} pulseCount={pulseMap[a.id] || 0} />
        ))}

        {/* Consensus Hub Component */}
        <g transform={`translate(${HUB_CX},${HUB_CY})`}>
          <motion.circle r={38} fill="rgba(8,12,25,1)" stroke="var(--violet)" strokeWidth={hubActive ? 4 : 2}
            animate={{ scale: hubActive ? 1.15 : 1 }}
            style={{ filter: hubActive ? 'drop-shadow(0 0 25px var(--violet))' : 'none', transition: 'all 0.4s' }}
          />
          <text textAnchor="middle" y={-5} style={{ fontSize: '20px' }}>⚖️</text>
          <text textAnchor="middle" y={18} fill="var(--violet)" style={{ fontSize: '10px', fontWeight: 900, fontFamily: 'Outfit', letterSpacing: '2px' }}>HUB</text>
          {hubActive && (
             <motion.circle r={38} fill="none" stroke="var(--violet)" strokeWidth={1}
               initial={{ scale: 1, opacity: 0.8 }}
               animate={{ scale: 3.5, opacity: 0 }}
               transition={{ duration: 1.5, repeat: Infinity }}
             />
          )}
        </g>

        {/* Active Agent Nodes */}
        {agentList.map(a => (
          <AgentNode key={a.id} agent={a} active={(now - a.lastAct) < 3000} pulseCount={pulseMap[a.id] || 0} />
        ))}
      </svg>
    </div>
  );
}
