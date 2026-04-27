import React from 'react';
import { GlassPanel, SectionHeader, DataRow } from './ui/SovereignUI';
import { fmt } from './SharedUI';

/** ⚠️ Sovereign Risk Desk — GAP Protocol drawdown ladders + escalation matrix */

const LEVEL_COLORS = {
  NORMAL:          'var(--emerald)',
  YELLOW:          'var(--amber)',
  ORANGE:          '#ff7b00',
  RED:             'var(--red)',
  CIRCUIT_BREAKER: 'var(--red)',
};

function AccountLadder({ type, data = {} }) {
  const color   = LEVEL_COLORS[data.level] || 'var(--mid)';
  const allowed = data.allowed !== false;

  return (
    <div style={{
      padding: '10px',
      background: 'rgba(0,0,0,0.3)',
      border: `1px solid rgba(255,255,255,0.05)`,
      borderTop: `2px solid ${color}`,
      borderRadius: '6px',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <span className="fw-900 c-top uppercase ls-w" style={{ fontSize: '0.6rem' }}>{type} Ladder</span>
        <span className="badge-sovereign" style={{ color, borderColor: color }}>{data.level ?? 'NORMAL'}</span>
      </div>
      <DataRow label="Peak Equity"    value={`$${fmt(data.peak ?? 0, 0)}`} />
      <DataRow label="Current Equity" value={`$${fmt(data.current ?? 0, 0)}`} color="top" />
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
        <div className={allowed ? 'pulse' : ''}
          style={{ width: '6px', height: '6px', borderRadius: '50%', background: allowed ? 'var(--emerald)' : 'var(--red)', flexShrink: 0 }} />
        <span className="fw-700 c-mid uppercase" style={{ fontSize: '0.55rem' }}>
          {allowed ? 'TRADING AUTHORIZED' : 'LOCKED OUT'}
        </span>
      </div>
    </div>
  );
}

export default function RiskDesk({ gap = {} }) {
  const esc = gap?.escalation || {};
  const dd  = gap?.drawdown   || {};

  return (
    <GlassPanel style={{ borderLeft: '2px solid var(--red)' }}>
      <SectionHeader
        title="Sovereign Risk Desk (GAP Protocols)"
        icon="⚠️"
        sub="Institutional Guard"
      />

      <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>

        {/* Drawdown Ladders */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <AccountLadder type="IBKR" data={dd.ibkr || {}} />
          <AccountLadder type="PROP" data={dd.prop || {}} />
        </div>

        {/* GAP-12 Escalation Matrix */}
        <div style={{
          padding: '12px',
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '6px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span className="fw-900 c-mid uppercase ls-w" style={{ fontSize: '0.6rem' }}>GAP-12 Escalation Matrix</span>
            {esc.paper_forced && (
              <span className="badge-sovereign c-red" style={{ borderColor: 'var(--red)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="pulse" style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--red)' }} />
                FORCED PAPER
              </span>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: '16px', rowGap: '4px' }}>
            <DataRow
              label="Consec. Losses"
              value={esc.losses ?? 0}
              color={esc.losses >= 2 ? 'red' : 'top'}
            />
            <DataRow
              label="Win Streak"
              value={esc.streak ?? 0}
              color={esc.streak >= 3 ? 'emerald' : 'top'}
            />
            <DataRow
              label="Audit Status"
              value={esc.audit_required ? 'REQUIRED' : 'CLEAR'}
              color={esc.audit_required ? 'red' : 'emerald'}
            />
            <DataRow
              label="Action"
              value={esc.allowed === true ? 'EXECUTE' : esc.allowed === false ? 'PAUSED' : 'STANDBY'}
              color={esc.allowed === true ? 'emerald' : esc.allowed === false ? 'red' : 'dim'}
            />
          </div>
        </div>

      </div>
    </GlassPanel>
  );
}
