import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { fmt } from './SharedUI';
import { GlassPanel, SectionHeader, StatusBadge } from './ui/SovereignUI';

/** ⚡ Neural HFT Tape — live tick feed with market-data fallback & price-flash */

// Fallback symbols when no live data yet
const CORE_SYMBOLS = ['SPY', 'QQQ', 'IWM'];

/**
 * Hook: returns the previous value of `val` and whether it went up, down, or unchanged.
 * Used to drive the price-flash animation.
 */
function usePriceFlash(val, tickId) {
  const prev = useRef(val);
  const [dir, setDir] = useState(null); // 'up' | 'down' | 'pulse' | null

  useEffect(() => {
    if (val == null) return;
    if (prev.current != null) {
      if (val > prev.current) setDir('up');
      else if (val < prev.current) setDir('down');
      else setDir('pulse');
    } else {
      setDir('pulse');
    }
    prev.current = val;
    const t = setTimeout(() => setDir(null), 150);
    return () => clearTimeout(t);
  }, [val, tickId]);

  return dir;
}

function TickCell({ sym, tickData, marketData }) {
  const history    = marketData || [];
  const lastBar    = history.length ? history[history.length - 1] : null;
  const price      = tickData?.price ?? lastBar?.close ?? null;
  const prevClose  = history.length > 1 ? history[history.length - 2]?.close : null;
  const rawChange  = tickData?.change_pct
    ?? (price != null && prevClose != null ? ((price - prevClose) / prevClose) * 100 : null);
  // Only show direction badge when we have a real change value
  const hasChange  = rawChange != null;
  const change     = rawChange ?? 0;
  const isUp       = change >= 0;
  const flashDir   = usePriceFlash(price, tickData?.timestamp || tickData?.id);

  const flashBg =
    flashDir === 'up'    ? 'rgba(0,255,170,0.2)' :
    flashDir === 'down'  ? 'rgba(255,51,102,0.2)' :
    flashDir === 'pulse' ? 'rgba(255,255,255,0.08)' :
    'rgba(255,255,255,0.02)';

  const mode = tickData ? 'LIVE' : history.length ? 'HIST' : 'WAIT';
  const modeColor = mode === 'LIVE' ? 'var(--cyan)' : mode === 'HIST' ? 'var(--amber)' : 'var(--dim)';

  return (
    <motion.div
      whileHover={{ scale: 1.02, borderColor: 'rgba(255,255,255,0.12)' }}
      animate={{ background: flashBg }}
      transition={{ background: { duration: 0.4 } }}
      style={{
        padding: '10px',
        borderRadius: '8px',
        border: '1px solid rgba(255,255,255,0.05)',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        cursor: 'default',
        width: '100%',
      }}
    >
      {/* Symbol + change badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="fw-900 c-top font-outfit" style={{ fontSize: '0.72rem' }}>{sym}</span>
        {hasChange ? (
          <span
            className={`font-mono fw-800 ${isUp ? 'c-emerald' : 'c-red'}`}
            style={{
              fontSize: '0.58rem',
              padding: '2px 6px',
              background: isUp ? 'rgba(0,255,170,0.06)' : 'rgba(255,51,102,0.06)',
              borderRadius: '4px',
            }}
          >
            {isUp ? '▲' : '▼'} {Math.abs(change).toFixed(2)}%
          </span>
        ) : (
          <span className="font-mono c-dim" style={{ fontSize: '0.5rem', padding: '2px 6px' }}>
            -- %
          </span>
        )}
      </div>

      {/* Price */}
      <div
        className={`font-mono fw-900 ${flashDir === 'up' ? 'c-emerald' : flashDir === 'down' ? 'c-red' : 'c-top'}`}
        style={{
          fontSize: '1.15rem',
          letterSpacing: '-0.03em',
          transition: 'color 0.4s',
          textShadow: flashDir ? '0 0 10px currentColor' : 'none',
        }}
      >
        {price != null
          ? `$${fmt(price)}`
          : <span className="c-dim" style={{ fontSize: '0.8rem' }}>---</span>}
      </div>

      {/* Footer */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        opacity: 0.5, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '4px',
      }}>
        <span className="fw-800 uppercase" style={{ fontSize: '0.45rem', color: 'var(--dim)' }}>
          Vol: {tickData?.volume != null ? fmt(tickData.volume, 0)
               : lastBar?.volume != null ? fmt(lastBar.volume, 0)
               : '---'}
        </span>
        <span className="font-mono fw-900" style={{ fontSize: '0.45rem', color: modeColor }}>
          {mode}
        </span>
      </div>
    </motion.div>
  );
}

export default function NeuralTape({ ticks = {}, market = {} }) {
  // Collect ALL symbols from live ticks + market data, preserving order
  const tickSyms   = Object.keys(ticks);
  const marketSyms = Object.keys(market);
  const allSyms    = [...new Set([...CORE_SYMBOLS, ...tickSyms, ...marketSyms])];
  const symbols    = allSyms.filter(s => ticks[s] || market[s]);
  const displaySyms = symbols.length > 0 ? symbols : CORE_SYMBOLS;
  const liveCount  = displaySyms.filter(s => ticks[s]).length;

  return (
    <GlassPanel style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1, minHeight: 0 }}>
      <SectionHeader
        title="HFT Neural Tape"
        sub="100Hz RAW TELEMETRY"
        icon="⚡"
        right={
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <StatusBadge
              label={liveCount > 0 ? `${liveCount} LIVE` : 'SYNC MODE'}
              status={liveCount > 0 ? 'active' : 'nominal'}
              color={liveCount > 0 ? 'cyan' : 'amber'}
            />
          </div>
        }
      />

      <div
        className="scrollbar-hide"
        style={{
          padding: '10px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          overflowY: 'auto',
          flex: 1,
        }}
      >
        <AnimatePresence initial={false}>
          {displaySyms.map(sym => (
            <motion.div
              key={sym}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              style={{ flex: '1 1 140px', minWidth: '140px', display: 'flex' }}
            >
              <TickCell
                sym={sym}
                tickData={ticks[sym]}
                marketData={market[sym]}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </GlassPanel>
  );
}
