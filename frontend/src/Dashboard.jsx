import React from 'react';
import MainLayout from './layout/MainLayout';
import { SidebarHeader, BudgetPanel } from './components/modules/SidebarModules';
import TacticalObservatory from './components/modules/TacticalObservatory';
import RightAnalyticsPanel from './components/modules/RightAnalyticsPanel';
import { GlassPanel, SectionHeader, StatusBadge } from './components/ui/SovereignUI';
import QuantumMinds from './components/QuantumMinds';

/** Lightweight error boundary — silently swallows render errors in sub-panels */
class PanelBoundary extends React.Component {
  state = { crashed: false };
  static getDerivedStateFromError() { return { crashed: true }; }
  componentDidCatch(err) { console.warn('[PanelBoundary] caught:', err?.message); }
  render() {
    if (this.state.crashed) {
      return (
        <div style={{ padding: '12px 16px', fontSize: '0.55rem', color: 'var(--dim)', fontFamily: 'monospace', letterSpacing: '0.08em' }}>
          PANEL SYNC ERROR — AWAITING DATA
        </div>
      );
    }
    return this.props.children;
  }
}

/** 🪐 SOVEREIGN DASHBOARD | v1.0-beta-beta
 *  Three-column institutional command center.
 */

const AGENT_COLORS = {
  agent_a: 'cyan', agent_b: 'violet', agent_c: 'amber',
  agent_d: 'emerald', agent_e: 'red',
};
const getAgentColor = (id) => AGENT_COLORS[id] || 'mid';

const COMPONENT_COLORS = {
  ONLINE: 'emerald', OFFLINE: 'red', STANDBY: 'amber',
};

// ── Health Components Bar (v1.0-beta-beta Memoized) ──
const HealthBar = React.memo(({ components = {}, health = {} }) => (
  <GlassPanel style={{ padding: '8px 16px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
      <span className="fw-900 c-dim uppercase ls-w" style={{ fontSize: '0.5rem', marginRight: '4px' }}>
        SYSTEM HEALTH
      </span>
      {Object.entries(components).map(([name, status]) => {
        const color = COMPONENT_COLORS[status] || 'dim';
        return (
          <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <div className={status === 'ONLINE' ? 'pulse' : ''} style={{
              width: '5px', height: '5px', borderRadius: '50%',
              background: `var(--${color})`,
              boxShadow: status === 'ONLINE' ? `0 0 6px var(--${color})` : 'none',
            }} />
            <span className="fw-800 uppercase font-mono" style={{ fontSize: '0.5rem', color: `var(--${color})` }}>
              {name.toUpperCase()}
            </span>
          </div>
        );
      })}
      <span style={{ marginLeft: 'auto', fontSize: '0.5rem', color: 'var(--dim)', fontFamily: 'JetBrains Mono, monospace' }}>
        MODE: {health.mode ?? '---'} · DMS: {health.dms ?? '---'} · LAT: {health.latency_ms ?? 0}ms
      </span>
    </div>
  </GlassPanel>
));

export default function Dashboard({
  data, ticks, eventQueue, activityMap, pulseMap,
  connected, logs, activeSym, setActive, sysTime,
}) {
  const { brain = {}, oracle = {}, health = {}, market = {} } = data || {};
  const activeData = market[activeSym] ?? [];
  const agents     = brain.agents ?? {};
  const components = health.components ?? {};

  // ── Left Sidebar ──
  const sidebarL = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <SidebarHeader connected={connected} sysTime={sysTime} uptime={health.up_time ?? 0} />

      {/* Health summary */}
      <HealthBar components={components} health={health} />

      {/* Autonomous Agent Mesh */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SectionHeader title="Autonomous Agent Mesh" sub={`${Object.keys(agents).length} ACTIVE ENTITIES`} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          {Object.entries(agents).sort(([a], [b]) => a.localeCompare(b)).map(([id, agent]) => (
            <GlassPanel key={id} style={{ borderLeft: `2px solid var(--${getAgentColor(id)})`, padding: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                <span className="fw-900 c-top font-outfit uppercase" style={{ fontSize: '0.6rem' }}>
                  {id.replace('agent_', '').replace('Agent_', '').replace('Risk_', 'R').toUpperCase()}
                </span>
                <div className={agent?.status === 'ACTIVE' || agent?.status === 'SYNCHRONIZED' ? 'pulse' : ''}
                  style={{
                    width: '4px', height: '4px', borderRadius: '50%',
                    background: agent?.status === 'ACTIVE' || agent?.status === 'SYNCHRONIZED'
                      ? `var(--${getAgentColor(id)})` : 'var(--dim)',
                  }} />
              </div>
              <div className="font-mono c-mid uppercase" style={{ fontSize: '0.48rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {agent?.status || 'AWAITING'}
              </div>
              <div style={{ width: '100%', height: '1px', background: 'rgba(255,255,255,0.03)', margin: '4px 0' }} />
              <div className="fw-800 c-dim font-mono" style={{ fontSize: '0.42rem', height: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {agent?.last_action || agent?.message || 'LINKED'}
              </div>
            </GlassPanel>
          ))}
        </div>
      </div>

      {/* Budget Panel */}
      <PanelBoundary><BudgetPanel budget={brain.gap?.budget} /></PanelBoundary>

      {/* Quantum Minds */}
      <PanelBoundary><QuantumMinds minds={brain.minds} activityMap={activityMap} eventQueue={eventQueue} /></PanelBoundary>
    </div>
  );

  // ── Center ──
  const center = (
    <TacticalObservatory
      activeSym={activeSym}
      setActive={setActive}
      market={market}
      activeData={activeData}
      oracle={oracle}
      brain={brain}
      ticks={ticks}
      logs={logs}
      eventQueue={eventQueue}
      activityMap={activityMap}
      pulseMap={pulseMap}
      connected={connected}
      health={health}
    />
  );

  // ── Right Panel ──
  const panelR = (
    <PanelBoundary>
      <RightAnalyticsPanel
        oracle={oracle}
        gap={brain.gap}
        brain={brain}
      />
    </PanelBoundary>
  );

  return (
    <div style={{ position: 'relative', height: '100vh', width: '100vw', background: 'var(--bg-main)', overflow: 'hidden' }}>
      {/* Atmospheric Backdrop */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden', zIndex: 0 }}>
        <div className="scanline" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '1px', background: 'rgba(255,255,255,0.04)' }} />
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at 50% 50%, rgba(0,229,255,0.02) 0%, transparent 70%)' }} />
      </div>

      <MainLayout sidebarL={sidebarL} center={center} panelR={panelR} />

      <style>{`
        @keyframes scanline { from { transform: translateY(-100vh); } to { transform: translateY(100vh); } }
        .scanline { animation: scanline 12s linear infinite; }
      `}</style>
    </div>
  );
}
