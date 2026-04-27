import React, { useMemo } from 'react';
import { useSystemStream } from '../../hooks/useSystemStream';
import { useEventEngine } from '../../hooks/useEventEngine';
import IntelligenceBus from './IntelligenceBus';
import BrainStateMachine from './BrainStateMachine';
import AgentInteractionGraph from './AgentInteractionGraph';
import OracleCausationGraph from './OracleCausationGraph';
import DataPipelineFlow from './DataPipelineFlow';
import LearningLoop from './LearningLoop';
import CognitiveMindsLayer from './CognitiveMindsLayer';

/** 🪐 SOVEREIGN ARCHITECTURE | v1.0-beta REAL-TIME MIRROR 🪐
 *  A unified observatory grid visualizing all core backend cognitive layers.
 */

export default function SovereignArchitecture({ data: propBrain, oracle: propOracle, health: propHealth, eventQueue: propQueue, connected: propConnected }) {
  // Only open a standalone WS when no parent is providing data (i.e. component is embedded standalone).
  // When propBrain is provided (even as {}) we treat it as parented — pass null to disable.
  const isParented = propBrain !== undefined && propBrain !== null;
  const wsUrl = useMemo(() => isParented ? null : `ws://${window.location.hostname}:8000/ws`, [isParented]);
  const { data: stream, connected: streamConnected } = useSystemStream(wsUrl);

  const connected = propConnected ?? streamConnected;
  const brain  = isParented ? (propBrain ?? {}) : (stream.brain ?? {});
  // When parented, use the oracle/health passed from the parent Dashboard context
  const oracle = isParented ? (propOracle ?? stream.oracle ?? {}) : (stream.oracle ?? {});
  const health = isParented ? (propHealth ?? stream.health ?? {}) : (stream.health ?? {});

  // Normalize event stream (Shared engine logic)
  const { activityMap, pulseMap } = useEventEngine(propQueue || [], 200);
  const activeQueue = propQueue || [];

  const PANEL = {
    background: 'rgba(6,9,16,0.92)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '12px',
    overflow: 'visible',
    backdropFilter: 'blur(20px)',
    transition: 'border-color 0.3s',
  };
  // Panels that contain SVGs need clip; others should expand naturally
  const PANEL_CLIP = { ...PANEL, overflow: 'hidden' };

  return (
    <div className="sovereign-observatory" style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px' }}>

      {/* ── ROW 1: Intelligence Bus (3fr) + Cognitive Minds (2fr) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '16px' }}>
        <div style={PANEL_CLIP}><IntelligenceBus eventQueue={activeQueue} activityMap={activityMap} /></div>
        <div style={PANEL_CLIP}><CognitiveMindsLayer brain={brain} health={health} activityMap={activityMap} pulseMap={pulseMap} /></div>
      </div>

      {/* ── ROW 2: Brain State Machine (2fr) + Agent Network (3fr) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 3fr', gap: '16px' }}>
        <div style={{ ...PANEL_CLIP, display: 'flex', flexDirection: 'column' }}><BrainStateMachine brain={brain} activityMap={activityMap} /></div>
        <div style={PANEL_CLIP}><AgentInteractionGraph brain={brain} eventQueue={activeQueue} activityMap={activityMap} pulseMap={pulseMap} /></div>
      </div>

      {/* ── ROW 3: Oracle Causation Map — full width ── */}
      <div>
        <div style={PANEL_CLIP}>
          <OracleCausationGraph oracle={oracle} activityMap={activityMap} />
        </div>
      </div>

      {/* ── ROW 4: Data Pipeline (3fr) + Learning Loop (2fr) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '16px' }}>
        <div style={PANEL_CLIP}><DataPipelineFlow brain={brain} health={health} activityMap={activityMap} /></div>
        <div style={PANEL}><LearningLoop brain={brain} eventQueue={activeQueue} activityMap={activityMap} /></div>
      </div>

      <style>{`
        .sovereign-observatory { background: transparent !important; }
      `}</style>
    </div>
  );
}
