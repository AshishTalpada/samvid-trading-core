import React from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Layers3,
  ListChecks,
  ShieldAlert,
} from 'lucide-react';
import { GlassPanel, SectionHeader } from './ui/SovereignUI';

const money = (value) => {
  const n = Number(value || 0);
  const sign = n > 0 ? '+' : '';
  return `${sign}$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

const pct = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;

const colorFor = (value) => {
  const n = Number(value || 0);
  if (n > 0) return 'var(--emerald)';
  if (n < 0) return 'var(--red)';
  return 'var(--mid)';
};

function Metric({ label, value, sub, tone = 'cyan', icon: Icon = Activity }) {
  return (
    <div className="truth-metric">
      <div className="truth-metric-icon" style={{ color: `var(--${tone})` }}>
        <Icon size={15} strokeWidth={2.4} />
      </div>
      <div>
        <div className="truth-metric-label">{label}</div>
        <div className="truth-metric-value" style={{ color: `var(--${tone})` }}>{value}</div>
        {sub && <div className="truth-metric-sub">{sub}</div>}
      </div>
    </div>
  );
}

function Bar({ label, value, total, tone = 'cyan' }) {
  const width = total > 0 ? Math.min(100, Math.max(2, (value / total) * 100)) : 0;
  return (
    <div className="truth-bar-row">
      <div className="truth-bar-meta">
        <span>{label}</span>
        <b>{value}</b>
      </div>
      <div className="truth-bar-track">
        <div className="truth-bar-fill" style={{ width: `${width}%`, background: `var(--${tone})` }} />
      </div>
    </div>
  );
}

export function TruthLayer({ truth = {} }) {
  const performance = truth.performance || {};
  const tasks = truth.tasks || {};
  const outcomes = truth.outcomes || [];
  const openBySymbol = truth.open_by_symbol || [];
  const recentTrades = truth.recent_trades || [];
  const orderHealth = truth.order_health || {};
  const taskStatuses = tasks.by_status || {};
  const taskTotal = Number(tasks.total || 0);
  const totalOutcomeRows = outcomes.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const orphaned = outcomes.find((row) => row.outcome === 'ORPHANED')?.count || 0;
  const openCount = outcomes.find((row) => row.outcome === 'OPEN')?.count || 0;

  return (
    <GlassPanel style={{ padding: 0, overflow: 'hidden' }}>
      <SectionHeader
        title="Truth Layer"
        icon={<ListChecks size={15} />}
        sub="Backend accounting, task state, execution residue"
        right={<span>{performance.updated_at ? `Updated ${performance.updated_at}` : 'Awaiting performance row'}</span>}
      />

      <div className="truth-grid">
        <div className="truth-column truth-column-wide">
          <div className="truth-metric-grid">
            <Metric
              label="Net PnL"
              value={money(performance.net_pnl)}
              sub={`${performance.closed_count || 0} resolved records`}
              tone={Number(performance.net_pnl || 0) >= 0 ? 'emerald' : 'red'}
              icon={BarChart3}
            />
            <Metric
              label="Win Rate"
              value={pct(performance.win_rate)}
              sub={`${performance.wins || 0} wins / ${performance.losses || 0} losses`}
              tone="cyan"
              icon={CheckCircle2}
            />
            <Metric
              label="Open Trades"
              value={openCount}
              sub={`${openBySymbol.length} symbols with exposure records`}
              tone={openCount > 0 ? 'amber' : 'emerald'}
              icon={Layers3}
            />
            <Metric
              label="Task Load"
              value={taskTotal}
              sub={`${taskStatuses.running || 0} running / ${taskStatuses.killed || 0} killed`}
              tone={taskStatuses.killed > taskStatuses.completed ? 'amber' : 'cyan'}
              icon={Clock3}
            />
          </div>

          <div className="truth-section">
            <div className="truth-section-title">
              <ShieldAlert size={14} />
              Outcome Distribution
            </div>
            <div className="truth-bars">
              {outcomes.slice(0, 8).map((row) => (
                <Bar
                  key={`${row.outcome}-${row.mode}`}
                  label={`${row.outcome} / ${row.mode}`}
                  value={row.count}
                  total={totalOutcomeRows}
                  tone={row.outcome === 'OPEN' ? 'amber' : row.outcome === 'ORPHANED' ? 'red' : 'cyan'}
                />
              ))}
              {outcomes.length === 0 && <div className="truth-empty">No trade outcomes reported yet.</div>}
            </div>
          </div>
        </div>

        <div className="truth-column">
          <div className="truth-section-title">
            <AlertTriangle size={14} />
            Integrity Warnings
          </div>
          <div className="truth-warning-list">
            <div className="truth-warning">
              <span>Orphaned trade records</span>
              <b style={{ color: orphaned > 0 ? 'var(--red)' : 'var(--emerald)' }}>{orphaned}</b>
            </div>
            <div className="truth-warning">
              <span>Persistent orders</span>
              <b>{orderHealth.persistent_orders || 0}</b>
            </div>
            <div className="truth-warning">
              <span>Unresolved order cache</span>
              <b style={{ color: orderHealth.stale_orders > 0 ? 'var(--amber)' : 'var(--emerald)' }}>
                {orderHealth.stale_orders || 0}
              </b>
            </div>
            <div className="truth-warning">
              <span>Failure post-mortems</span>
              <b style={{ color: orderHealth.failures > 0 ? 'var(--amber)' : 'var(--emerald)' }}>
                {orderHealth.failures || 0}
              </b>
            </div>
          </div>

          <div className="truth-section compact">
            <div className="truth-section-title">Open Exposure</div>
            <div className="truth-table">
              {openBySymbol.slice(0, 8).map((row) => (
                <div className="truth-table-row" key={row.symbol}>
                  <b>{row.symbol}</b>
                  <span>{row.count} rec</span>
                  <span>{Number(row.shares || 0).toFixed(0)} sh</span>
                </div>
              ))}
              {openBySymbol.length === 0 && <div className="truth-empty">No open exposure records.</div>}
            </div>
          </div>
        </div>

        <div className="truth-column truth-column-wide">
          <div className="truth-section-title">Recent Execution Records</div>
          <div className="truth-trade-list">
            {recentTrades.slice(0, 9).map((trade) => (
              <div className="truth-trade" key={trade.id}>
                <div>
                  <b>{trade.symbol || '---'}</b>
                  <span>{trade.direction || '---'} / {trade.pattern || '---'}</span>
                </div>
                <div>
                  <strong style={{ color: colorFor(trade.pnl) }}>{money(trade.pnl)}</strong>
                  <span>{trade.outcome || 'UNKNOWN'} / {trade.broker || '---'}</span>
                </div>
              </div>
            ))}
            {recentTrades.length === 0 && <div className="truth-empty">No execution records reported.</div>}
          </div>
        </div>
      </div>

      <style>{`
        .truth-grid {
          display: grid;
          grid-template-columns: minmax(360px, 1.2fr) minmax(260px, 0.8fr) minmax(340px, 1fr);
          gap: 12px;
          padding: 12px;
        }
        .truth-column {
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .truth-metric-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
        }
        .truth-metric {
          min-height: 78px;
          border: 1px solid rgba(255,255,255,0.06);
          background: rgba(255,255,255,0.025);
          border-radius: 6px;
          padding: 10px;
          display: grid;
          grid-template-columns: 28px minmax(0, 1fr);
          gap: 8px;
          align-items: center;
        }
        .truth-metric-icon {
          width: 28px;
          height: 28px;
          display: grid;
          place-items: center;
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 6px;
          background: rgba(0,0,0,0.22);
        }
        .truth-metric-label,
        .truth-section-title,
        .truth-bar-meta,
        .truth-warning,
        .truth-table-row,
        .truth-trade span,
        .truth-empty {
          font-family: JetBrains Mono, monospace;
        }
        .truth-metric-label {
          color: var(--dim);
          font-size: 0.48rem;
          font-weight: 900;
          text-transform: uppercase;
        }
        .truth-metric-value {
          font-family: Outfit, sans-serif;
          font-size: 1.1rem;
          font-weight: 900;
          line-height: 1.1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .truth-metric-sub {
          color: var(--dim);
          font-size: 0.52rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .truth-section {
          border: 1px solid rgba(255,255,255,0.06);
          background: rgba(0,0,0,0.18);
          border-radius: 6px;
          padding: 10px;
        }
        .truth-section.compact {
          flex: 1;
        }
        .truth-section-title {
          display: flex;
          align-items: center;
          gap: 7px;
          color: var(--top);
          font-size: 0.58rem;
          font-weight: 900;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 8px;
        }
        .truth-bars,
        .truth-warning-list,
        .truth-table,
        .truth-trade-list {
          display: flex;
          flex-direction: column;
          gap: 7px;
        }
        .truth-bar-meta,
        .truth-warning,
        .truth-table-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 8px;
          color: var(--mid);
          font-size: 0.54rem;
          font-weight: 800;
          min-width: 0;
        }
        .truth-bar-track {
          height: 5px;
          border-radius: 999px;
          background: rgba(255,255,255,0.045);
          overflow: hidden;
        }
        .truth-bar-fill {
          height: 100%;
          border-radius: 999px;
          opacity: 0.78;
        }
        .truth-warning,
        .truth-table-row,
        .truth-trade {
          border: 1px solid rgba(255,255,255,0.05);
          background: rgba(255,255,255,0.02);
          border-radius: 5px;
          padding: 7px 8px;
        }
        .truth-table-row span {
          color: var(--dim);
        }
        .truth-trade {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(96px, 0.42fr);
          gap: 10px;
          align-items: center;
        }
        .truth-trade div {
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .truth-trade b,
        .truth-trade strong {
          color: var(--top);
          font-family: Outfit, sans-serif;
          font-size: 0.72rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .truth-trade span {
          color: var(--dim);
          font-size: 0.5rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .truth-empty {
          color: var(--dim);
          font-size: 0.55rem;
          padding: 8px;
        }
        @media (max-width: 1320px) {
          .truth-grid { grid-template-columns: 1fr; }
          .truth-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (max-width: 720px) {
          .truth-metric-grid { grid-template-columns: 1fr; }
          .truth-trade { grid-template-columns: 1fr; }
        }
      `}</style>
    </GlassPanel>
  );
}
