import React from 'react';
import DhatuStateRing from '../DhatuStateRing';
import OracleGraph from '../OracleGraph';
import RiskDesk from '../RiskDesk';
import NeuralCalibration from '../NeuralCalibration';
import PortfolioMatrix from '../PortfolioMatrix';
import EvolutionaryIntelligence from '../EvolutionaryIntelligence';
import { GlassPanel, SectionHeader, DataRow } from '../ui/SovereignUI';
import { fmt } from '../SharedUI';

/** 📊 Analytics Panel (Right Sidebar - v1.0-beta) */

export default function RightAnalyticsPanel({ oracle = {}, gap = {}, brain = {} }) {
  const agentD = brain.agents?.agent_d || {};
  const agentB = brain.agents?.agent_b || {};
  const agentC = brain.agents?.agent_c || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* 🔮 ORACLE CORE */}
      <GlassPanel style={{ borderLeft: '2px solid var(--violet)' }}>
        <SectionHeader title="Oracle Reasoning" icon="🔮" sub="Dhatu State Matrix" />
        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <DhatuStateRing oracle={oracle} />
          <div style={{
            padding: '10px 12px',
            background: 'rgba(192,132,252,0.05)',
            borderLeft: '2px solid rgba(192,132,252,0.4)',
            borderRadius: '4px',
            fontStyle: 'italic',
            fontSize: '0.63rem',
            color: 'var(--top)',
            fontFamily: 'Outfit, sans-serif',
            lineHeight: '1.5',
          }}>
            "{oracle.reasoning ?? 'Synchronizing with global macro verticals...'}"
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <DataRow label="Theme"  value={oracle.theme  ?? '---'} color="violet" />
            <DataRow label="Nodes"  value={`${(oracle.nodes ?? []).length} connected`} color="dim" />
            <DataRow label="Edges"  value={`${(oracle.edges ?? []).length} causal links`} color="dim" />
          </div>
        </div>
      </GlassPanel>

      {/* 🌀 ORACLE GRAPH */}
      <GlassPanel style={{ background: 'rgba(0,0,0,0.6)', minHeight: '300px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <SectionHeader title="Live Macro Scent Graph" icon="🌀" />
        <div style={{ flexGrow: 1, position: 'relative' }}>
          <OracleGraph data={oracle} />
        </div>
      </GlassPanel>

      {/* 📈 PORTFOLIO MATRIX */}
      <PortfolioMatrix brain={brain} />

      {/* ⚠️ RISK DESK */}
      <RiskDesk gap={gap} />

      {/* 🤖 AGENT D — Neural Calibration */}
      <GlassPanel style={{ borderLeft: '2px solid var(--emerald)' }}>
        <SectionHeader title="Agent D — Self-Learning" icon="🧬" sub={agentD.status ?? 'CALIBRATING'} />
        <div style={{ padding: '8px', paddingTop: 0 }}>
          <DataRow label="Memory"         value={agentD.memory       ?? '0 Trades'}  color="emerald" />
          <DataRow label="Top Pattern"    value={agentD.top_pattern   ?? '---'}       color="cyan" />
          <DataRow label="Sig. Gate"      value={agentD.threshold_gate ?? 'OFFLINE'}  color="amber" />
          <DataRow label="Calibration"    value={agentD.calibration   ?? 'OFFLINE'}  color="dim" />
        </div>
      </GlassPanel>

      {/* 🧬 NEURAL CALIBRATION TABLE */}
      <NeuralCalibration rates={agentD.learned_rates} />

      {/* 🧬 EVOLUTIONARY INTELLIGENCE (GAP-44) */}
      <EvolutionaryIntelligence evolution={gap?.evolution} />

      {/* 🤖 AGENT B — Classifier */}
      <GlassPanel style={{ borderLeft: '2px solid var(--violet)' }}>
        <SectionHeader title={`${agentB.label || 'Agent B'} — Classifier`} icon="🔮" sub={agentB.status ?? 'ACTIVE'} />
        <div style={{ padding: '8px', paddingTop: 0 }}>
          <DataRow label="Classifier"   value={agentB.classifier ?? 'DhatuClassifier v1.0-beta'} color="violet" />
          <DataRow label="Risk Mod"     value={(() => { const m = Number(agentB.modifier); return isNaN(m) ? '---' : `${(m > 1 ? m : m * 100).toFixed(0)}%`; })()} color="amber" />
          <DataRow label="Oracle Freeze" value={agentB.freeze ? 'YES — FROZEN' : 'NO'}   color={agentB.freeze ? 'red' : 'emerald'} />
        </div>
      </GlassPanel>

      {/* 🤖 AGENT C — Executor */}
      <GlassPanel style={{ borderLeft: '2px solid var(--amber)' }}>
        <SectionHeader title={`${agentC.label || 'Agent C'} — Executor`} icon="⚔️" sub={agentC.status ?? 'ACTIVE'} />
        <div style={{ padding: '8px', paddingTop: 0 }}>
          <DataRow label="MT5 Status"   value={agentC.mt5        ?? 'Standby'}  color={agentC.mt5 === 'Connected' ? 'emerald' : 'dim'} />
          <DataRow label="Black Swan"   value={agentC.blackswan  ?? 'Watching'} color={agentC.blackswan === 'ACTIVE' ? 'red' : 'amber'} />
          <DataRow label="VIX Protocol" value={agentC.vix_protocol ?? 'Standby'} color="cyan" />
          <DataRow label="Portfolio Guard" value={agentC.guard   ?? '20% Rsv'} color="dim" />
        </div>
      </GlassPanel>

      {/* 🛰️ FOOTER */}
      <div style={{
        marginTop: '8px',
        paddingTop: '12px',
        borderTop: '1px solid var(--border)',
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}>
        <span style={{ fontSize: '0.45rem', color: 'var(--dim)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.12em' }}>
          Institutional High-Frequency Dashboard
        </span>
        <span style={{ fontSize: '0.6rem', fontWeight: 900, color: 'var(--mid)', fontFamily: 'Outfit, sans-serif', letterSpacing: '-0.02em' }}>
          SINGULARITY MATRIX · v1.0-beta
        </span>
      </div>

    </div>
  );
}
