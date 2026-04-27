import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

/** 🏛️ SOVEREIGN QUORUM MATRIX V5.0 | HIGH-RESOLUTION LIVE COMPONENT
 *  Hard-wired to WebSocket consensus stream with dynamic scaling.
 */

const DEFAULT_AGENTS = [
  { id: 'agent_a', label: 'A', name: 'Pattern_Atlas',     color: '#00e5ff', icon: '📡' },
  { id: 'agent_b', label: 'B', name: 'Belief_Tracker',    color: '#d4a5ff', icon: '🧿' },
  { id: 'agent_c', label: 'C', name: 'Portfolio_Guard',   color: '#ffcc00', icon: '🛡️' },
  { id: 'agent_d', label: 'D', name: 'Regime_Mind',       color: '#00ffaa', icon: '📊' },
  { id: 'agent_e', label: 'E', name: 'Correlation_Guard', color: '#ff3366', icon: '🧬' },
  { id: 'agent_f', label: 'F', name: 'Volatility_Oracle', color: '#ff9900', icon: '🌪️' },
  { id: 'agent_g', label: 'G', name: 'Architect_Mind',    color: '#ffffff', icon: '🏛️' },
  { id: 'risk_guard', label: 'R', name: 'Safety_Protocol', color: '#ff0000', icon: '⚠️' },
  { id: 'dhatu_oracle', label: 'O', name: 'Macro_Truth',   color: '#9d00ff', icon: '🕉️' },
  { id: 'swarm_predictor', label: 'S', name: 'Mass_Logic', color: '#00ffcc', icon: '🐝' },
  { id: 'mind_ultrathink', label: 'U', name: 'Deep_Reason', color: '#ff00ff', icon: '🧠' },
];

const getAgentMetadata = (id) => {
  const meta = DEFAULT_AGENTS.find(a => a.id === id);
  if (meta) return meta;
  // Dynamic fallback for new agents
  return {
    id,
    label: id.replace('agent_', '').toUpperCase().slice(0,1),
    name: id.toUpperCase(),
    color: '#8899ac',
    icon: '🤖'
  };
};

const CX = 250, CY = 250;
const R_OUTER = 220, R_INNER = 145;
const GAP_DEG = 2.5;

function polar(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function arcPath(cx, cy, rOut, rIn, startDeg, endDeg) {
  const [x1, y1] = polar(cx, cy, rOut, startDeg);
  const [x2, y2] = polar(cx, cy, rOut, endDeg);
  const [x3, y3] = polar(cx, cy, rIn,  endDeg);
  const [x4, y4] = polar(cx, cy, rIn,  startDeg);
  const large = (endDeg - startDeg) > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${rOut} ${rOut} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${rIn} ${rIn} 0 ${large} 0 ${x4} ${y4} Z`;
}

// ── Internal Components ──

function AgentArcSegment({ agent, idx, n, voteInfo, isPulsing, hasVoted }) {
  const sliceDeg = (360 / n) - GAP_DEG;
  const startDeg = idx * (360 / n) + GAP_DEG / 2;
  const endDeg   = startDeg + sliceDeg;
  const isYes = voteInfo?.vote === 'YES';
  
  const col = hasVoted ? (isYes ? '#00ffaa' : '#ff3366') : isPulsing ? agent.color : 'rgba(255,255,255,0.06)';
  
  const fullPath = arcPath(CX, CY, R_OUTER, R_INNER, startDeg, endDeg);
  const midDeg = startDeg + sliceDeg / 2;
  const [lx, ly] = polar(CX, CY, R_OUTER + 22, midDeg);

  return (
    <g>
      <path d={fullPath} fill="rgba(255,255,255,0.03)" />
      <motion.path d={fullPath} fill={col}
        animate={{ opacity: hasVoted ? 1 : isPulsing ? 0.6 : 0.2 }}
        style={{ filter: hasVoted ? `drop-shadow(0 0 10px ${col})` : 'none', transition: 'all 0.4s' }}
      />
      {isPulsing && (
        <motion.path d={fullPath} fill="none" stroke={agent.color} strokeWidth="2"
          animate={{ opacity: [0.8, 0, 0.8], scale: [1, 1.02, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          style={{ transformOrigin: `${CX}px ${CY}px` }}
        />
      )}
      <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle"
        fill={hasVoted ? col : isPulsing ? agent.color : '#4a5568'}
        style={{ fontSize: '14px', fontWeight: 900, fontFamily: 'JetBrains Mono', transition: 'fill 0.3s' }}>
        {agent.label}
      </text>
    </g>
  );
}

function DecisionCore({ pct, decision, phase, yesCount, n }) {
  const color = pct >= 75 ? '#00ffaa' : pct >= 50 ? '#ffcc00' : '#ff3366';
  return (
    <g transform={`translate(${CX},${CY})`}>
      <defs>
        <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%"    stopColor={`${color}10`} />
          <stop offset="80%"   stopColor={`${color}05`} />
          <stop offset="100%"  stopColor="transparent" />
        </radialGradient>
      </defs>
      <circle r={140} fill="url(#core-glow)" />
      <motion.circle cx={0} cy={0} r={120} fill="rgba(5,7,12,0.98)" stroke={color} strokeWidth={2}
        animate={{ scale: phase !== 'IDLE' ? [1, 1.03, 1] : 1 }}
        transition={{ duration: 2, repeat: Infinity }}
      />
      <text y={-25} textAnchor="middle" fill={color} style={{ fontSize: '52px', fontWeight: 900, fontFamily: 'Outfit' }}>
        {pct}%
      </text>
      <text y={15} textAnchor="middle" fill="rgba(255,255,255,0.4)" style={{ fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '3px' }}>
        CONSENSUS
      </text>
      <text y={45} textAnchor="middle" fill={color} style={{ fontSize: '18px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px' }}>
        {decision}
      </text>
      <text y={75} textAnchor="middle" fill="rgba(255,255,255,0.3)" style={{ fontSize: '9px', fontWeight: 700 }}>
        {yesCount} / {n} QUORUM
      </text>
    </g>
  );
}

export default function QuorumMatrix({ eventQueue = [], activityMap = {}, brain = {} }) {
  const [consensus, setConsensus] = useState(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 800);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const ev = [...eventQueue].reverse().find(e => e.type === 'consensus.update');
    if (ev?.data) setConsensus(ev.data);
  }, [eventQueue]);

  const votes    = consensus?.agent_tally || consensus?.votes || [];
  const voteMap  = Object.fromEntries(votes.map(v => [v.agent, v]));
  
  // Deriving dynamic agent list from votes + defaults
  const currentAgentIds = Array.from(new Set([...DEFAULT_AGENTS.map(a => a.id), ...votes.map(v => v.agent)]));
  const activeAgents = currentAgentIds.map(getAgentMetadata);
  const n = activeAgents.length;
  
  const yesCount = votes.filter(v => v.vote === 'YES').length;
  const pct      = n > 0 ? Math.round((yesCount / n) * 100) : 0;
  const phase    = consensus?.phase || 'SYNCHRONIZED';
  const scanTarget = brain?.scan_target;
  const isScanning = (now - (brain?.scan_timestamp || 0)) < 2500;
  
  // Debug log to trace pulse arrival
  useEffect(() => {
    if (isScanning) {
      console.log(`[Matrix] Scanning detected: ${scanTarget} (delta: ${now - (brain.scan_timestamp || 0)}ms)`);
    }
  }, [isScanning, scanTarget, now, brain.scan_timestamp]);
  
  const symbol   = consensus?.symbol || scanTarget || '---';
  
  // Intelligence Priority Logic: 
  // 1. If we have a LIVE consensus (less than 5s old) AND the symbol matches the current scan target
  // 2. Otherwise if scanning, show SCANNING
  // 3. Otherwise show AWAITING SIGNAL
  const consensusSymbol = consensus?.symbol;
  const isSymbolMismatch = consensusSymbol && scanTarget && consensusSymbol !== scanTarget;
  const ts = Number(consensus?.timestamp);
  const isConsensusLive = consensus && !isNaN(ts) && (now - ts) < 5000 && !isSymbolMismatch;
  
  let decision = 'AWAITING SIGNAL';
  if (isConsensusLive) {
      if (consensus.phase === 'EVALUATING') decision = `EVALUATING ${symbol}`;
      else if (consensus.phase === 'FRICTION_VETO') decision = `REJECT (RR DRAG)`;
      else if (consensus.phase === 'QUORUM_INIT') decision = `VOTING ${symbol}`;
      else decision = consensus.decision || consensus.phase;
  } else if (isScanning && scanTarget) {
      decision = `SCANNING ${scanTarget}`;
  } else if (consensus && !isScanning) {
      // Stale consensus or mismatch
      decision = 'AWAITING SIGNAL';
  }
  
  const displaySymbol = (isConsensusLive || isScanning) ? symbol : '---';
  
  // Clear votes if we are showing scanning or awaiting signal
  const activeVotes = isConsensusLive ? votes : [];
  const activeVoteMap = Object.fromEntries(activeVotes.map(v => [v.agent, v]));

  return (
    <div style={{ background: 'rgba(2,4,8,0.7)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
       {/* Live Header */}
       <div style={{ padding: '15px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <motion.div animate={{ opacity: phase !== 'IDLE' ? [1, 0.4, 1] : 0.4 }} 
            style={{ width: 12, height: 12, borderRadius: '50%', background: phase !== 'IDLE' ? 'var(--emerald)' : 'var(--dim)', boxShadow: phase !== 'IDLE' ? '0 0 15px var(--emerald)' : 'none' }} />
          <span style={{ fontSize: '0.85rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            Quorum Matrix <span style={{ color: 'var(--amber)', fontSize: '0.65rem' }}>[{displaySymbol}]</span>
          </span>
        </div>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
           <span style={{ fontSize: '0.65rem', color: 'var(--dim)', fontWeight: 800, fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>{decision}</span>
           <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.1)' }} />
           <span style={{ fontSize: '0.65rem', color: 'var(--cyan)', fontWeight: 900, fontFamily: 'JetBrains Mono' }}>V5.0 LIVE</span>
        </div>
      </div>

      <div style={{ padding: '25px', display: 'flex', gap: '40px', alignItems: 'center', flex: 1 }}>
        <div style={{ flexShrink: 0 }}>
          <svg width="480" height="480" viewBox="0 0 500 500" style={{ overflow: 'visible' }}>
            {activeAgents.map((agent, i) => (
              <AgentArcSegment key={agent.id} idx={i} n={n} agent={agent} 
                voteInfo={activeVoteMap[agent.id]} hasVoted={!!activeVoteMap[agent.id]} 
                isPulsing={(now - (activityMap[agent.id] || 0)) < 3000} />
            ))}
            <DecisionCore pct={pct} decision={decision} phase={phase} yesCount={yesCount} n={n} />
          </svg>
        </div>

        {/* Live Detail Feed */}
        <div className="custom-scrollbar" style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr', gap: '10px', alignContent: 'start', overflowY: 'auto', paddingRight: '5px' }}>
           <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '5px' }}>Member Tally</div>
           {activeAgents.map(agent => {
             const v = voteMap[agent.id];
             const act = (now - (activityMap[agent.id] || 0)) < 3000;
             return (
               <div key={agent.id} style={{ 
                 display: 'flex', alignItems: 'center', justifyContent: 'space-between', 
                 padding: '10px 18px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px',
                 border: '1px solid rgba(255,255,255,0.04)',
                 borderLeft: `4px solid ${v ? (v.vote === 'YES' ? '#00ffaa' : '#ff3366') : act ? agent.color : 'rgba(255,255,255,0.05)'}`,
                 transition: 'all 0.3s'
               }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '16px' }}>{agent.icon}</span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#fff', fontFamily: 'Outfit' }}>{agent.id.replace('Agent_', '').replace('Mind_', '')}</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.68rem', fontWeight: 900, color: v ? (v.vote === 'YES' ? '#00ffaa' : '#ff3366') : act ? agent.color : 'var(--dim)', fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>
                      {v ? v.vote : act ? 'THINKING' : 'IDLE'}
                    </div>
                    {v && v.confidence && (
                      <div style={{ fontSize: '0.5rem', color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>
                        {(v.confidence * 100).toFixed(0)}% CONF
                      </div>
                    )}
                  </div>
               </div>
             );
           })}
        </div>
      </div>
    </div>
  );
}
