import React, { useMemo, useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/** ⚡ Intelligence Bus Monitor V3.0 — Large lane display */

const EVENT_CONFIG = {
  'tick.hft':           { color: '#00e5ff', icon: '⚡', label: 'HFT TICK',        lane: 0 },
  'candle.batch':       { color: '#00e5ff', icon: '🕯️', label: 'CANDLE BATCH',    lane: 0 },
  'trade.entry':        { color: '#00ffaa', icon: '📈', label: 'TRADE ENTRY',      lane: 1 },
  'trade.exit':         { color: '#ffcc00', icon: '🚪', label: 'TRADE EXIT',       lane: 1 },
  'consensus.update':   { color: '#ffcc00', icon: '⚖️', label: 'CONSENSUS',        lane: 1 },
  'oracle.state':       { color: '#d4a5ff', icon: '🔮', label: 'ORACLE STATE',     lane: 2 },
  'oracle.freeze':      { color: '#ff3366', icon: '🛑', label: 'ORACLE FREEZE',    lane: 2 },
  'news.hft':           { color: '#fbbf24', icon: '📰', label: 'NEWS FEED',        lane: 2 },
  'mind.dialogue':      { color: '#d4a5ff', icon: '🧠', label: 'MIND DIALOGUE',    lane: 2 },
  'calibration.update': { color: '#00ffaa', icon: '🧬', label: 'CALIBRATION',      lane: 3 },
  'system.state':       { color: '#ffffff', icon: '🛰️', label: 'SYSTEM STATE',     lane: 0 },
  'full_state':         { color: '#ffffff', icon: '🛰️', label: 'FULL SYNC',        lane: 0 },
};
const DEFAULT_CFG = { color: '#8899ac', icon: '●', label: 'EVENT', lane: 0, speed: 1.0 };

const LANES = [
  { label: 'DATA FLOW',  color: '#00e5ff', desc: 'Ticks · Candles · State' },
  { label: 'TRADE BUS',  color: '#ffcc00', desc: 'Entries · Exits · Consensus' },
  { label: 'ORACLE BUS', color: '#d4a5ff', desc: 'Oracle · Minds · Freeze' },
  { label: 'LEARNING',   color: '#00ffaa', desc: 'Calibration · Evolution' },
];

function PacketStream({ laneIndex, packets }) {
  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
      <AnimatePresence>
        {packets.filter(p => (EVENT_CONFIG[p.type] || DEFAULT_CFG).lane === laneIndex).slice(0, 15).map((p, pi) => {
          const cfg = EVENT_CONFIG[p.type] || DEFAULT_CFG;
          return (
            <motion.circle key={p.id}
              r={5} cy={31} fill={cfg.color}
              style={{ filter: `drop-shadow(0 0 8px ${cfg.color})` }}
              initial={{ cx: 30, opacity: 0 }}
              animate={{ cx: '95%', opacity: [0, 1, 1, 0] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.8 + pi * 0.3, ease: 'linear' }}
            />
          );
        })}
      </AnimatePresence>
    </svg>
  );
}

export default function IntelligenceBus({ eventQueue = [] }) {
  const [packets,    setPackets]    = useState([]);
  const [throughput, setThroughput] = useState(0);
  const [avgLatency, setLatency]    = useState(0);
  const [laneLatest, setLaneLatest] = useState([null, null, null, null]);
  const evCounter  = useRef(0);
  const latBuf     = useRef([]);

  // 1s throughput window
  useEffect(() => {
    const t = setInterval(() => {
      setThroughput(evCounter.current);
      evCounter.current = 0;
      if (latBuf.current.length > 0) {
        setLatency(Math.round(latBuf.current.reduce((a, b) => a + b, 0) / latBuf.current.length));
        latBuf.current = [];
      }
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // New event intake
  useEffect(() => {
    if (!eventQueue.length) return;
    const ids = new Set(packets.map(p => p.id));
    const fresh = eventQueue.filter(e => !ids.has(e.id));
    if (!fresh.length) return;
    evCounter.current += fresh.length;
    fresh.forEach(ev => {
      if (ev.timestamp) {
        // V3.1: True Latency Mapping — No longer capping at 999ms to ensure system lag is visible.
        latBuf.current.push(Date.now() - ev.timestamp);
      }
    });
    setPackets(prev => [...fresh, ...prev].slice(0, 40));
    // Update latest per lane
    setLaneLatest(prev => {
      const next = [...prev];
      fresh.forEach(ev => {
        const cfg = EVENT_CONFIG[ev.type] || DEFAULT_CFG;
        next[cfg.lane] = ev;
      });
      return next;
    });
  }, [eventQueue, packets]);

  // Lane counts
  const laneCounts = useMemo(() => {
    const c = [0, 0, 0, 0];
    eventQueue.slice(0, 60).forEach(ev => { c[(EVENT_CONFIG[ev.type] || DEFAULT_CFG).lane]++; });
    return c;
  }, [eventQueue]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0', background: 'rgba(2,5,10,0.3)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
      {/* ── Header ── */}
      <div style={{
        padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(0,0,0,0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className={throughput > 0 ? 'pulse' : ''} style={{ width: 10, height: 10, borderRadius: '50%', background: throughput > 0 ? 'var(--cyan)' : 'var(--dim)', boxShadow: throughput > 0 ? '0 0 12px var(--cyan)' : 'none' }} />
          <span style={{ fontSize: '0.82rem', fontWeight: 900, color: '#fff', fontFamily: 'Outfit', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
            Intelligence Bus Monitor <span style={{ color: 'var(--cyan)', opacity: 0.6 }}>LIVE</span>
          </span>
        </div>
        <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase' }}>Flow Rate</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: throughput > 0 ? 'var(--cyan)' : 'var(--dim)', fontFamily: 'JetBrains Mono' }}>
              {throughput} <span style={{ fontSize: '0.65rem' }}>PKT/S</span>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--dim)', fontWeight: 900, textTransform: 'uppercase' }}>Latency</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: 'var(--amber)', fontFamily: 'JetBrains Mono' }}>
              {avgLatency} <span style={{ fontSize: '0.65rem' }}>MS</span>
            </div>
          </div>
        </div>
      </div>

      <div style={{ padding: '0' }}>
        {LANES.map((lane, li) => {
          const latest = laneLatest[li];
          const latCfg = latest ? (EVENT_CONFIG[latest.type] || DEFAULT_CFG) : null;
          const isLive = throughput > 0 && laneCounts[li] > 0;
          
          return (
            <div key={lane.label} style={{
              display: 'flex', borderBottom: li < 3 ? '1px solid rgba(255,255,255,0.04)' : 'none',
              background: isLive ? 'rgba(255,255,255,0.01)' : 'transparent',
              transition: 'background 0.4s',
            }}>
              {/* Lane Info */}
              <div style={{ width: '180px', padding: '12px 20px', borderRight: '1px solid rgba(255,255,255,0.04)', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: isLive ? lane.color : 'var(--dim)' }} />
                  <span style={{ fontSize: '0.72rem', fontWeight: 900, color: isLive ? '#fff' : 'var(--dim)', fontFamily: 'Outfit', textTransform: 'uppercase' }}>
                    {lane.label}
                  </span>
                </div>
                <span style={{ fontSize: '0.55rem', color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {lane.desc}
                </span>
              </div>

              {/* Packet stream area */}
              <div style={{ flex: 1, position: 'relative', height: '64px', overflow: 'hidden' }}>
                {!isLive && (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem', color: 'rgba(255,255,255,0.15)', fontFamily: 'JetBrains Mono', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.2em' }}>
                    NEURAL LINK ESTABLISHED · SYNCING DATA
                  </div>
                )}

                {/* Latest event badge */}
                <AnimatePresence>
                  {latest && (
                    <motion.div key={latest.id} initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ opacity: 0 }}
                      style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 14px', borderRadius: '20px', border: `1px solid ${latCfg.color}60`, background: `${latCfg.color}18`, zIndex: 10 }}>
                      <span style={{ fontSize: '16px' }}>{latCfg.icon}</span>
                      <span style={{ fontSize: '0.68rem', fontWeight: 900, color: latCfg.color, fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>
                        {latCfg.label}
                      </span>
                      {latest.data?.symbol && (
                        <span style={{ fontSize: '0.62rem', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono', opacity: 0.8 }}>
                          [{latest.data.symbol}]
                        </span>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                <PacketStream laneIndex={li} packets={packets} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
