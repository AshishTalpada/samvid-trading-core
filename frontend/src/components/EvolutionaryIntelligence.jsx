import React from 'react';
import { GlassPanel, SectionHeader, DataRow } from './ui/SovereignUI';

/** 🧬 GAP-44: Evolutionary Intelligence Display */
export default function EvolutionaryIntelligence({ evolution = {} }) {
  const evolutionEntries = Object.entries(evolution);
  
  if (evolutionEntries.length === 0) {
    return (
      <GlassPanel style={{ borderLeft: '2px solid var(--amber)', opacity: 0.6 }}>
        <SectionHeader title="Evolutionary Intelligence" icon="🧬" sub="AWAITING 10 TRADES" />
        <div style={{ padding: '8px', fontSize: '0.55rem', color: 'var(--dim)', fontStyle: 'italic', textAlign: 'center' }}>
          Collecting trade snapshots for initial population...
        </div>
      </GlassPanel>
    );
  }

  return (
    <GlassPanel style={{ borderLeft: '2px solid var(--amber)' }}>
      <SectionHeader 
        title="Evolutionary Intelligence" 
        icon="🧬" 
        sub="GAP-44 FEEDBACK LOOP" 
      />
      <div style={{ padding: '8px', paddingTop: 0 }}>
        {evolutionEntries.map(([param, data]) => {
          // Format parameter names for display
          const displayName = param
            .replace(/_/g, ' ')
            .replace('SYSTEM', '')
            .trim()
            .toUpperCase();

          return (
            <div key={param} style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '4px' }}>
              <DataRow 
                label={displayName} 
                value={data.value} 
                color="amber" 
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 4px', marginTop: '1px' }}>
                <span style={{ fontSize: '0.4rem', color: 'var(--dim)', fontFamily: 'monospace' }}>
                  CONF: {(data.confidence * 100).toFixed(1)}%
                </span>
                <span style={{ fontSize: '0.4rem', color: 'var(--dim)', opacity: 0.5 }}>
                  UPD: {(() => {
                    const lu = data.last_updated;
                    if (!lu || typeof lu !== 'string') return '---';
                    // v1.0-beta-beta: Robust time extraction
                    const parts = lu.split('T');
                    if (parts.length < 2) return lu.slice(-8); // Fallback to last 8 chars if not ISO
                    return parts[1].split('.')[0];
                  })()}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}
