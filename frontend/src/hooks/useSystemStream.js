import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useSystemStream v1.0-beta-beta - The SETO Global Event Engine
 * High-performance event routing, queueing (up to 500 events),
 * and batched state synchronization for real-time cognitive visualization.
 *
 * v1.0-beta-beta changes: individual event types (oracle.state, system.state, candle.batch,
 * calibration.update, consensus.update, trade.*) now update the relevant
 * slice of state so all components stay live between full_state syncs.
 */
export function useSystemStream(url) {
  const [data, setData] = useState({ brain: {}, health: {}, oracle: {}, market: {}, ticks: {}, activityMap: {}, latestEvent: null });
  const [eventQueue, setEventQueue] = useState([]);
  const [connected, setConnected] = useState(false);
  const [stateStatus, setStateStatus] = useState({ hydrated: false, error: null, lastSync: null });

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const statePollRef = useRef(null);

  // High-performance mutable storage for batching — v1.0-beta-beta: Immutable deep-cloning
  const batchState = useRef({ brain: null, health: null, oracle: null, market: null, event: null, ticks: null, activityMap: null });
  const localQueue = useRef([]);
  const MAX_QUEUE_SIZE = 5000; // Increased for HFT bursts

  const processBatch = useCallback(() => {
    // 1. Process State Updates (Throttled to ~30fps)
    const { brain, health, oracle, market, event, ticks, activityMap } = batchState.current;
    if (brain || health || oracle || market || event || ticks || activityMap) {
      setData(prev => {
        // Deep clone market/ticks to prevent component reference-equality bypass
        const nextMarket = market ? { ...prev.market, ...market } : prev.market;
        const nextTicks  = ticks  ? { ...prev.ticks,  ...ticks  } : prev.ticks;
        
        return {
          brain: brain ? { ...prev.brain, ...brain } : prev.brain,
          health: health ? { ...prev.health, ...health } : prev.health,
          oracle: oracle ? { ...prev.oracle, ...oracle } : prev.oracle,
          market: nextMarket,
          ticks: nextTicks,
          activityMap: activityMap ? { ...prev.activityMap, ...activityMap } : prev.activityMap,
          latestEvent: event ?? prev.latestEvent,
        };
      });
      // Atomic reset after commit
      batchState.current = { brain: null, health: null, oracle: null, market: null, event: null, ticks: null, activityMap: null };
    }

    // 2. Sync Event Queue (Batch UI commits)
    if (localQueue.current.length > 0) {
      setEventQueue(prev => {
        // v1.0-beta-beta: Sequential append with size cap
        const next = [...localQueue.current, ...prev].slice(0, MAX_QUEUE_SIZE);
        localQueue.current = [];
        return next;
      });
    }
  }, []);

  useEffect(() => {
    const t = setInterval(processBatch, 33); // ~30Hz batching
    return () => clearInterval(t);
  }, [processBatch]);

  const hydrateState = useCallback(async () => {
    if (!url || url.includes('null')) return;
    try {
      const stateUrl = new URL(url);
      stateUrl.protocol = stateUrl.protocol === 'wss:' ? 'https:' : 'http:';
      stateUrl.pathname = '/state';
      stateUrl.search = '';

      const headers = {};
      const secret = import.meta.env.VITE_API_SERVER_KEY;
      if (secret) headers['X-Sovereign-Key'] = secret;

      const res = await fetch(stateUrl.toString(), { headers });
      if (!res.ok) {
        setStateStatus({ hydrated: false, error: `state ${res.status}`, lastSync: null });
        return;
      }
      const d = await res.json();
      if (d.brain && Object.keys(d.brain).length > 0) batchState.current.brain = { ...d.brain };
      if (d.health && Object.keys(d.health).length > 0) batchState.current.health = { ...d.health };
      if (d.oracle && Object.keys(d.oracle).length > 0) batchState.current.oracle = { ...d.oracle };
      if (d.market && Object.keys(d.market).length > 0) batchState.current.market = { ...d.market };
      const event = {
        type: 'state.snapshot',
        id: `state-${Date.now()}`,
        data: d,
        timestamp: Date.now(),
      };
      batchState.current.event = event;
      localQueue.current.push(event);
      setStateStatus({ hydrated: true, error: null, lastSync: new Date().toLocaleTimeString('en-US', { hour12: false }) });
    } catch (err) {
      setStateStatus({ hydrated: false, error: err?.message || 'state unavailable', lastSync: null });
      console.warn("State hydrate skipped:", err?.message || err);
    }
  }, [url]);

  const connect = useCallback(() => {
    if (!url || url.includes('null')) return;
    
    // v1.0-beta-beta: Dynamic Port discovery fallback
    let finalUrl = url;
    if (url.includes(':8000') && window.location.port && window.location.port !== '3000') {
       // If we are on a custom port, assume backend shifted too (Development/Tunneling)
       // console.log("[Matrix] Attempting port-discovery shift...");
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(finalUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        console.log("🌌 [Matrix Engine] Neural Link Synchronized.");
        hydrateState();
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          const d = msg.data || {};
           const now = Date.now();
           // Generate a deterministic ID based on timestamp + sequence to avoid Math.random() DOM thrashing
           const eventId = msg.id || `${now}-${Math.floor(Math.random() * 10000)}`;
 
           // ── Activity Map (Glows/Pulses) ──
           if (msg.type === 'system.pulse' || msg.type === 'tick.hft' || msg.type === 'consensus.update') {
              const node = d.agent || d.symbol || 'system';
              batchState.current.activityMap = { 
                ...(batchState.current.activityMap || {}), 
                [node]: now 
              };
           }

          // ── Full state sync (initial connect / periodic) ──
          if (msg.type === 'full_state' || msg.type === 'state') {
            if (d.brain && Object.keys(d.brain).length > 0) batchState.current.brain = { ...d.brain };
            if (d.health && Object.keys(d.health).length > 0) batchState.current.health = { ...d.health };
            if (d.oracle && Object.keys(d.oracle).length > 0) batchState.current.oracle = { ...d.oracle };
            if (d.market && Object.keys(d.market).length > 0) batchState.current.market = { ...d.market };
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── HFT Tick events ──
          if (msg.type === 'tick.hft' || msg.type === 'tick') {
            const tick = d.symbol ? d : msg;
            if (tick.symbol) {
              batchState.current.ticks = { ...(batchState.current.ticks || {}), [tick.symbol]: { ...tick } };
            }
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── Oracle state updates ──
          if (msg.type === 'oracle.state' || msg.type === 'oracle.update' || msg.type === 'oracle.freeze') {
            if (d && Object.keys(d).length > 0) {
              batchState.current.oracle = { ...d };
            }
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── System / brain state updates ──
          if (msg.type === 'system.state' || msg.type === 'brain.state') {
            if (d.brain && Object.keys(d.brain).length > 0) {
                batchState.current.brain = { 
                    ...(batchState.current.brain || {}), 
                    ...d.brain,
                    // Preserve agents explicitly if not sent in the payload
                    agents: d.brain.agents || (batchState.current.brain || {}).agents
                };
            }
            if (d.health && Object.keys(d.health).length > 0) batchState.current.health = { ...(batchState.current.health || {}), ...d.health };
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── System Pulse (Scan Targets) ──
          if (msg.type === 'system.pulse') {
            if (d.symbol) {
              batchState.current.brain = {
                ...(batchState.current.brain || {}),
                scan_target: d.symbol,
                scan_timestamp: now, // Use local time to avoid system clock drift issues
              };
            }
            // Pulses now go into the event queue so useEventEngine can see them
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return; 
          }

          // ── Candle batch ──
          if (msg.type === 'candle.batch') {
            const candleMap = d.candles ?? (d.symbol && Array.isArray(d.bars) ? { [d.symbol]: d.bars } : null);
            if (candleMap && typeof candleMap === 'object') {
              const merged = { ...(batchState.current.market || {}) };
              Object.entries(candleMap).forEach(([sym, bars]) => {
                if (Array.isArray(bars) && bars.length > 0) {
                   // v1.0-beta-beta: Merge by time to prevent overwriting history with deltas
                   const existing = merged[sym] || [];
                   const combined = [...existing];
                   bars.forEach(nb => {
                     const idx = combined.findIndex(eb => eb.time === nb.time);
                     if (idx >= 0) combined[idx] = nb;
                     else combined.push(nb);
                   });
                   // Cap at 2000 bars per symbol to prevent memory bloat
                   merged[sym] = combined.sort((a,b) => (a.time > b.time ? 1 : -1)).slice(-2000);
                }
              });
              batchState.current.market = merged;
            }
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── Consensus update ──
          if (msg.type === 'consensus.update') {
            if (d && Object.keys(d).length > 0) {
              batchState.current.brain = {
                ...(batchState.current.brain || {}),
                consensus: { ...d },
                state: d.phase || (batchState.current.brain || {}).state,
              };
            }
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── Calibration update ──
          if (msg.type === 'calibration.update') {
            if (d && Object.keys(d).length > 0) {
              const prevBrain = batchState.current.brain || {};
              batchState.current.brain = {
                ...prevBrain,
                agents: {
                  ...(prevBrain.agents || {}),
                  agent_d: { ...((prevBrain.agents || {}).agent_d || {}), ...d, status: 'SYNCHRONIZED' },
                },
              };
            }
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── Trade events ──
          if (msg.type === 'trade.entry' || msg.type === 'trade.exit') {
            if (d && Object.keys(d).length > 0) {
              const prevBrain = batchState.current.brain || {};
              batchState.current.brain = {
                ...prevBrain,
                pnl_session: d.pnl_session ?? prevBrain.pnl_session,
                positions_count: d.positions_count ?? prevBrain.positions_count,
                last_trade: { ...d },
              };
            }
            batchState.current.event = { ...msg, id: eventId };
            localQueue.current.push({ ...msg, id: eventId, timestamp: now });
            return;
          }

          // ── All other named events ──
          if (msg.type || msg.event) {
            const event = msg.event ? { ...msg.event, id: eventId, timestamp: now } : { ...msg, id: eventId, timestamp: now };
            batchState.current.event = event;
            localQueue.current.push(event);
          }
        } catch (err) {
          console.warn("Matrix Desync:", err, e.data);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (reconnectRef.current) clearTimeout(reconnectRef.current);
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    } catch (err) {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      reconnectRef.current = setTimeout(connect, 3000);
    }
  }, [url, hydrateState]);

  useEffect(() => {
    connect();
    hydrateState();
    if (statePollRef.current) clearInterval(statePollRef.current);
    statePollRef.current = setInterval(hydrateState, 10000);
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (statePollRef.current) clearInterval(statePollRef.current);
    };
  }, [connect, hydrateState]);

  return { data, eventQueue, connected, stateStatus };
}
