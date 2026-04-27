import React from 'react';
import { GlassPanel, SectionHeader } from './ui/SovereignUI';
import { fmt } from './SharedUI';

/** 🧬 Neural Calibration — Agent D learned win-rate table */
export default function NeuralCalibration({ rates }) {
  const entries = Object.entries(rates || {}).slice(0, 15);

  return (
    <GlassPanel style={{ borderLeft: '2px solid var(--emerald)' }}>
      <SectionHeader
        title="Neural Experience Matrix (Agent D)"
        icon="🧬"
        sub={`${entries.length} LEARNED MODELS`}
      />

      <div style={{ padding: '0 8px 8px', maxHeight: '260px', overflowY: 'auto' }}>
        <table className="mkt-table">
          <thead>
            <tr>
              <th>Pattern · Regime</th>
              <th>Exp. WR</th>
              <th>Gate</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, wr]) => {
              const isHigh = wr >= 0.60;
              return (
                <tr key={key} className="transition-colors">
                  <td className="c-mid uppercase" style={{ letterSpacing: '-0.02em', fontSize: '0.58rem' }}>
                    {key.replace(/\|/g, ' · ')}
                  </td>
                  <td className={`fw-900 ${isHigh ? 'c-emerald' : 'c-amber'}`}>
                    {(wr * 100).toFixed(1)}%
                  </td>
                  <td className={wr >= 0.52 ? "c-emerald fw-800" : "c-amber fw-800"} style={{ fontSize: '0.5rem' }}>
                    {wr >= 0.52 ? "ENABLED" : "THROTTLED"}
                  </td>
                </tr>
              );
            })}

            {entries.length === 0 && (
              <tr>
                <td colSpan={3} className="text-center italic opacity-30"
                  style={{ paddingTop: '32px', paddingBottom: '32px', fontSize: '0.6rem', letterSpacing: '0.1em' }}>
                  Calibration Engine Cooling — Awaiting Memory Scent
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </GlassPanel>
  );
}
