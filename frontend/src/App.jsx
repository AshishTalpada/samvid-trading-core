import React, { useState, useEffect, useMemo } from 'react';
import { useSystemStream } from './hooks/useSystemStream';
import { useEventEngine } from './hooks/useEventEngine';
import Dashboard from './Dashboard';

async function generateHmacToken(secret) {
  const enc = new TextEncoder();
  // v1.0-beta-beta: Use 60s windows to reduce drift collision sensitivity, or implement multi-window attempt
  const ts = Math.floor(Date.now() / 1000 / 30);
  const key = await window.crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" },
    false, ["sign"]
  );
  const signature = await window.crypto.subtle.sign("HMAC", key, enc.encode(ts.toString()));
  return Array.from(new Uint8Array(signature)).map(b => b.toString(16).padStart(2, '0')).join('');
}

const getWsUrl = (token) => {
  const host = window.location.hostname || 'localhost';
  const port = window.location.port === '3000' ? '8000' : (window.location.port || '8000'); 
  const query = token ? `?token=${token}` : '';
  return `ws://${host}:${port}/ws${query}`;
};

/** Extract a meaningful one-liner from any backend event */
function extractMsg(ev) {
  if (!ev) return 'System pulse...';
  const d = ev.data || {};
  switch (ev.type) {
    case 'tick.hft':
      return `${d.symbol} @ $${(d.price || 0).toFixed(2)}  vol:${d.volume || 0}`;
    case 'news.hft':
      return `[NEWS] ${d.headline || '---'} (Impact: ${((d.impact || 0) * 10).toFixed(1)} / Snt: ${((d.sentiment || 0) * 10).toFixed(1)})`;
    case 'oracle.state':
      return `Dhatu: ${d.dhatu || '---'} | Conf: ${(((d.confidence || 0) * 100)).toFixed(0)}% | ${(d.summary || d.reasoning || '').slice(0, 60)}`;
    case 'calibration.update':
      return `Calibration: ${d.n_trades || 0} trades | Rating: ${d.data_rating || '---'} | Patterns: ${(d.top_patterns || []).slice(0, 2).join(', ')}`;
    case 'mind.dialogue':
      return `[${d.sender || 'Mind'}] ${d.message || d.content || d.text || 'Cognitive process update'}`;
    case 'consensus.update':
      const tally = d.agent_tally || d.votes || [];
      const yes = Array.isArray(tally) ? tally.filter(v => v.vote === 'YES').length : 0;
      return `Consensus: ${d.phase || d.decision || 'update'} [${d.symbol || '---'}] Yes: ${yes}/${tally.length || '?'}`;
    case 'candle.batch':
      return `Candle batch: ${(d.symbols || []).slice(0, 4).join(', ')} +${d.count || 0} bars stored`;
    case 'system.state': {
      const b = d.brain || {};
      return `State sync — Brain: ${b.state || '---'} | Regime: ${b.regime || '---'} | PnL: $${(b.pnl_session || 0).toFixed(0)}`;
    }
    case 'full_state': {
      const b = d.brain || {};
      const o = d.oracle || {};
      return `Full sync — Brain: ${b.state || '---'} | Dhatu: ${o.dhatu || '---'} | Pos: ${b.positions_count || 0}`;
    }
    default:
      return ev.msg || ev.text || ev.type || 'System update';
  }
}

/** Derive a log tag from event type */
function getTag(type) {
  if (!type) return 'SYSTEM';
  if (type.startsWith('tick')) return 'TICK';
  if (type.startsWith('news')) return 'NEWS';
  if (type.startsWith('oracle')) return 'ORACLE';
  if (type.startsWith('calibration')) return 'AGENT_D';
  if (type.startsWith('mind')) return 'MIND';
  if (type.startsWith('consensus')) return 'CONSENSUS';
  if (type.startsWith('candle')) return 'PIPELINE';
  if (type.startsWith('trade')) return 'TRADE';
  if (type.startsWith('system')) return 'SYSTEM';
  if (type === 'full_state') return 'SYNC';
  return type.split('.')[0].toUpperCase();
}

export default function App() {
  const [wsUrl, setWsUrl] = useState(null);
  const { data: stream, eventQueue, connected } = useSystemStream(wsUrl);
  const { activityMap, pulseMap } = useEventEngine(eventQueue, 100);

  const [logs, setLogs] = useState([]);
  const [activeSym, setActive] = useState('SPY');
  const [sysTime, setSysTime] = useState('');

  // ── INITIAL HANDSHAKE GATHERING ──
  useEffect(() => {
    const updateLink = async () => {
      const secret = import.meta.env.VITE_API_SERVER_KEY;
      if (secret) {
        const token = await generateHmacToken(secret);
        setWsUrl(getWsUrl(token));
      } else {
        setWsUrl(getWsUrl());
      }
    };
    updateLink();
    const t = setInterval(updateLink, 30000); // Refresh token every 30s
    return () => clearInterval(t);
  }, []);

  // Build intelligence log from every event that arrives
  useEffect(() => {
    if (!stream.latestEvent) return;
    const ev = stream.latestEvent;
    // Skip full_state spam — only log first sync per reconnect
    if (ev.type === 'full_state' && logs.length > 0) return;

    setLogs(prev => {
      // v1.0-beta-beta: Check for duplicate events by ID to prevent flicker
      if (prev.find(l => l.id === ev.id)) return prev;
      
      return [{
        id: ev.id || `${Date.now()}-${Math.random()}`,
        ts: new Date().toLocaleTimeString('en-US', { hour12: false }),
        tag: getTag(ev.type),
        msg: extractMsg(ev),
        type: ev.type,
      }, ...prev].slice(0, 200);
    });
  }, [stream.latestEvent]);

  // Add connection/disconnection log entries
  useEffect(() => {
    setLogs(prev => {
      const topType = prev[0]?.type;
      if (!connected && topType === 'system.disconnect') {
        return [{ ...prev[0], ts: new Date().toLocaleTimeString('en-US', { hour12: false }) }, ...prev.slice(1)];
      }
      // Use a stable ID for connection messages
      const statusId = connected ? `conn-${Date.now()}` : `disc-${Date.now()}`;
      return [{
        id: statusId,
        ts: new Date().toLocaleTimeString('en-US', { hour12: false }),
        tag: connected ? 'SYSTEM' : 'EMERGENCY',
        msg: connected ? 'Neural link established — streaming live backend data' : 'Neural link lost — attempting reconnect…',
        type: connected ? 'system.connect' : 'system.disconnect',
      }, ...prev].slice(0, 200);
    });
  }, [connected]);

  useEffect(() => {
    const t = setInterval(() => setSysTime(new Date().toLocaleTimeString('en-US', { hour12: false })), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <Dashboard
      data={stream}
      ticks={stream.ticks || {}}
      eventQueue={eventQueue}
      activityMap={activityMap}
      pulseMap={pulseMap}
      connected={connected}
      logs={logs}
      activeSym={activeSym}
      setActive={setActive}
      sysTime={sysTime}
    />
  );
}

