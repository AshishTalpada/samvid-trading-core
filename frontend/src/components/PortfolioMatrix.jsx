import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassPanel, SectionHeader } from './ui/SovereignUI';
import { fmt } from './SharedUI';

/** 📈 Portfolio Matrix — live position table */
export default function PortfolioMatrix({ brain = {} }) {
  const positions = brain.positions || [];
  const pnl       = brain.pnl_session ?? 0;
  const rawMod    = brain.agents?.agent_b?.modifier;
  const modifier  = (rawMod != null && !isNaN(Number(rawMod))) ? Number(rawMod) : 1.0;
  const guard     = brain.agents?.agent_c?.guard ?? '20% Rsv';

  return (
    <GlassPanel style={{ borderLeft: '2px solid var(--amber)' }}>
      <SectionHeader
        title="Portfolio Matrix"
        icon="📈"
        sub={`${positions.length} ACTIVE POSITION${positions.length !== 1 ? 'S' : ''}`}
      />

      <div style={{ padding: '0 8px 8px', overflowX: 'auto' }}>
        <table className="mkt-table">
          <thead>
            <tr>
              <th>SYMBOL</th>
              <th>SIZE</th>
              <th>AVG</th>
              <th>LAST</th>
              <th>PNL</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {positions.map((pos) => {
                const isUp = (pos.unrealized_pnl ?? 0) >= 0;
                return (
                  <motion.tr
                    key={pos.symbol}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <td className="fw-900 c-top">{pos.symbol}</td>
                    <td className="c-mid">{pos.position}</td>
                    <td className="c-dim">{pos.avg_price ? `$${fmt(pos.avg_price)}` : '---'}</td>
                    <td className="c-top">{pos.current_price ? `$${fmt(pos.current_price)}` : '---'}</td>
                    <td className={`fw-900 ${isUp ? 'c-emerald' : 'c-red'}`}>
                      {isUp ? '+' : ''}${fmt(pos.unrealized_pnl ?? 0)}
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>

            {positions.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center italic opacity-30" style={{ paddingTop: '24px', paddingBottom: '24px', fontSize: '0.6rem', letterSpacing: '0.1em' }}>
                  Portfolio Flat — Awaiting Execution
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* P&L summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', padding: '8px', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <div style={{ padding: '10px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
          <span style={{ display: 'block', fontSize: '0.55rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--dim)', marginBottom: '4px' }}>Session P&L</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 900, fontFamily: 'Outfit, sans-serif', color: pnl >= 0 ? 'var(--emerald)' : 'var(--red)' }}>
            {pnl >= 0 ? '+' : ''}${fmt(pnl)}
          </div>
          <div style={{ fontSize: '0.6rem', color: 'var(--dim)', marginTop: '4px', fontWeight: 700 }}>
            {brain.consecutive_losses ?? 0} LOSS STREAK
          </div>
        </div>

        <div style={{ padding: '10px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
          <span style={{ display: 'block', fontSize: '0.55rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--dim)', marginBottom: '4px' }}>Risk Modifier</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 900, fontFamily: 'Outfit, sans-serif', color: 'var(--amber)' }}>
            {(modifier > 1 ? modifier : modifier * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: '0.6rem', color: 'var(--dim)', marginTop: '4px', fontWeight: 700 }}>GUARD: {guard}</div>
        </div>
      </div>
    </GlassPanel>
  );
}
