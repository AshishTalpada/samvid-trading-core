import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Maps event types → architectural node IDs used by SystemFlowchart,
 * CognitiveMindsLayer, AgentInteractionGraph, DataPipelineFlow, etc.
 * This is the bridge between the WebSocket event stream and the visual activity pulses.
 */
const EVENT_TO_NODES = {
  'tick.hft':           ['ibkr', 'intel_bus'],
  'tick':               ['ibkr', 'intel_bus'],
  'candle.batch':       ['questdb', 'sqlite', 'pipeline', 'intel_bus'],
  'oracle.state':       ['oracle', 'swarm', 'intel_bus'],
  'oracle.freeze':      ['oracle'],
  'news.hft':           ['finnhub', 'intel_bus'],
  'calibration.update': ['agent_d', 'intel_bus'],
  'consensus.update':   ['consensus', 'intel_bus', 'agent_a', 'agent_b', 'agent_c', 'agent_d', 'agent_e', 'agent_f', 'agent_g', 'risk_guard', 'dhatu_oracle', 'swarm_predictor', 'mind_ultrathink'],
  'trade.entry':        ['consensus', 'exit_iq', 'intel_bus', 'agent_c'],
  'trade.exit':         ['exit_iq', 'dms_guard', 'intel_bus', 'agent_c'],
  'system.state':       ['intel_bus', 'agent_a', 'agent_b', 'agent_c', 'agent_d', 'agent_e', 'agent_f', 'agent_g', 'risk_guard', 'dhatu_oracle', 'swarm_predictor', 'mind_ultrathink'],
  'full_state':         ['intel_bus', 'agent_a', 'agent_b', 'agent_c', 'agent_d', 'agent_e', 'agent_f', 'agent_g', 'risk_guard', 'dhatu_oracle', 'swarm_predictor', 'mind_ultrathink'],
  'system.pulse':       ['intel_bus'],
};

/**
 * useEventEngine V3.0 — Activity tracking for all architectural visualization.
 * Indexes by both event type AND semantic node name so every component's
 * activityMap lookups resolve to a real timestamp.
 */
export function useEventEngine(messages = [], maxQueue = 100) {
  const [engineState, setEngineState] = useState({ activity: {}, pulses: {} });
  const lastProcessedId = useRef(null);

  useEffect(() => {
    if (!messages || messages.length === 0) return;

    // Find messages newer than our last processed message
    let newMessages = [];
    if (!lastProcessedId.current) {
      newMessages = messages;
    } else {
      const lastIndex = messages.findIndex(m => m.id === lastProcessedId.current);
      if (lastIndex === -1) {
        newMessages = messages;
      } else if (lastIndex > 0) {
        newMessages = messages.slice(0, lastIndex);
      }
    }

    if (newMessages.length === 0) return;
    lastProcessedId.current = messages[0]?.id;

    const now = Date.now();
    setEngineState(prev => {
      const nextActivity = { ...prev.activity };
      const nextPulses = { ...prev.pulses };

      newMessages.forEach(msg => {
        const type = msg.type;
        if (!type) return;

        // 1. Index by raw event type
        nextActivity[type] = now;

        // 2. Map to architectural node IDs
        const nodes = EVENT_TO_NODES[type] || [];
        nodes.forEach(n => { 
          nextActivity[n] = now; 
          nextPulses[n] = (nextPulses[n] || 0) + 1;
        });

        // 3. Special: mind.dialogue
        if (type === 'mind.dialogue') {
          const sender = (msg.data?.sender || msg.data?.mind || '').toLowerCase().replace(/\s+/g, '_');
          if (sender) {
            nextActivity[`mind_${sender}`] = now;
            nextActivity[sender] = now;
            nextActivity['intel_bus'] = now;
            nextPulses[`mind_${sender}`] = (nextPulses[`mind_${sender}`] || 0) + 1;
          }
        }

        // 3.1 Special: system.pulse (extract agent)
        if (type === 'system.pulse') {
          const agentId = (msg.data?.agent || '').toLowerCase();
          if (agentId) {
            nextActivity[agentId] = now;
            nextPulses[agentId] = (nextPulses[agentId] || 0) + 1;
          }
        }

        // 4. Special: always mark Intel Bus active
        nextActivity['intel_bus'] = now;
        nextPulses['intel_bus'] = (nextPulses['intel_bus'] || 0) + 1;

        // 5. Propagate to pipeline nodes
        if (type === 'tick.hft' || type === 'tick') {
          nextActivity['yfinance'] = now;
          nextPulses['yfinance'] = (nextPulses['yfinance'] || 0) + 1;
        }
        if (type === 'system.state' || type === 'full_state') {
          ['questdb','sqlite','pipeline','oracle','swarm','consensus'].forEach(n => {
            nextActivity[n] = now;
            nextPulses[n] = (nextPulses[n] || 0) + 1;
          });
        }

        // 6. Explicit meta nodes
        if (msg.meta?.nodes) {
          msg.meta.nodes.forEach(n => { 
            nextActivity[n] = now;
            nextPulses[n] = (nextPulses[n] || 0) + 1;
          });
        }
      });
      
      return { activity: nextActivity, pulses: nextPulses };
    });
  }, [messages]);

  return { activityMap: engineState.activity, pulseMap: engineState.pulses };
}

/**
 * useActivityDecay - Calculates opacity/glow intensity based on time elapsed 
 * since the last event of a specific type or node.
 */
export function useActivityDecay(activityMap, key, duration = 3000) {
  const [intensity, setIntensity] = useState(0);

  useEffect(() => {
    const update = () => {
      const lastTime = activityMap[key] || 0;
      const elapsed = Date.now() - lastTime;
      const strength = Math.max(0, 1 - (elapsed / duration));
      setIntensity(strength);
      
      if (strength > 0) {
        requestAnimationFrame(update);
      }
    };

    const frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [activityMap, key, duration]);

  return intensity;
}
