import React from 'react';
import TradingChart from '../TradingChart';
import IntelligenceLog from '../IntelligenceLog';
import NeuralTape from '../NeuralTape';
import StatCards from '../StatCards';
import SystemFlowchart from '../SystemFlowchart';
import SovereignArchitecture from '../architecture/SovereignArchitecture';
import QuorumMatrix from '../QuorumMatrix';
import { TruthLayer } from '../TruthLayer';
import { GlassPanel, SectionHeader, StatusBadge } from '../ui/SovereignUI';

/** 🔭 Tactical Observatory v1.0-beta-beta — Center Core */

const SYMBOLS = ['SPY', 'QQQ', 'IWM'];

export default function TacticalObservatory({
  activeSym, setActive, market, activeData,
  oracle, brain, ticks, logs, eventQueue, activityMap, pulseMap, connected, health,
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

      {/* ── TOP STATS ROW ── */}
      <StatCards oracle={oracle} brain={brain} market={market} ticks={ticks} />

      {/* ── QUORUM HUD (COMMERCIAL SHOWCASE) ── */}
      <QuorumMatrix eventQueue={eventQueue} activityMap={activityMap} brain={brain} />

      <TruthLayer truth={brain.truth} />

      {/* ── MIDDLE INTELLIGENCE LAYER ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '12px', minHeight: '550px' }}>

        {/* Chart (8 cols) */}
        <div style={{ gridColumn: 'span 8', display: 'flex', flexDirection: 'column' }}>
          <GlassPanel style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <SectionHeader
              title="Sovereign Tactical Chart"
              icon="📊"
              sub={`Active: ${activeSym}`}
              right={
                <div style={{ display: 'flex', gap: '6px' }}>
                  {SYMBOLS.map(s => (
                    <button
                      key={s}
                      onClick={() => setActive(s)}
                      style={{
                        padding: '4px 14px',
                        borderRadius: '4px',
                        fontSize: '0.6rem',
                        fontWeight: 900,
                        border: '1px solid',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        background:    activeSym === s ? 'rgba(0,229,255,0.12)' : 'transparent',
                        borderColor:   activeSym === s ? 'var(--cyan)' : 'rgba(255,255,255,0.1)',
                        color:         activeSym === s ? 'var(--cyan)'  : 'var(--dim)',
                        boxShadow:     activeSym === s ? '0 0 8px rgba(0,229,255,0.3)' : 'none',
                        letterSpacing: '0.08em',
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              }
            />
            <div style={{ flexGrow: 1, minHeight: 0 }}>
              <TradingChart symbol={activeSym} data={activeData} />
            </div>
          </GlassPanel>
        </div>

        {/* Neural Tape + Log (4 cols) */}
        <div style={{ gridColumn: 'span 4', display: 'flex', flexDirection: 'column', gap: '10px', minHeight: 0 }}>
          {/* NeuralTape gets both live ticks AND market history as fallback */}
          <NeuralTape ticks={ticks} market={market} />
          <IntelligenceLog logs={logs} />
        </div>
      </div>

      {/* ── TOPOLOGY LAYER ── */}
      <GlassPanel style={{ background: 'var(--bg-panel)', padding: 0 }}>
        <div style={{ width: '100%', height: '750px', overflow: 'hidden', position: 'relative', borderRadius: '12px' }}>
          <SystemFlowchart
            brain={brain}
            health={health}
            oracle={oracle}
            activityMap={activityMap}
            pulseMap={pulseMap}
            eventQueue={eventQueue}
          />
        </div>
      </GlassPanel>

      {/* ── SUBSYSTEM OBSERVATORY ── */}
      <GlassPanel style={{ background: 'var(--bg-panel)' }}>
        <SectionHeader
          title="Subsystem Observatory · Cognitive Mirror"
          icon="👁️"
          sub="7 Independent Modules · Live Backend Mirror"
        />
        <SovereignArchitecture
          data={brain}
          oracle={oracle}
          health={health}
          eventQueue={eventQueue}
          connected={connected}
        />
      </GlassPanel>

    </div>
  );
}
