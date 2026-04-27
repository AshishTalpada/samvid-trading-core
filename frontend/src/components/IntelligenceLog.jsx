import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const getTagColor = (tag) => {
  switch (tag?.toUpperCase()) {
    case 'SYSTEM': return 'var(--cyan)';
    case 'MATRIX': return 'var(--top)';
    case 'ORACLE': return 'var(--violet)';
    case 'AGENT_A': return 'var(--cyan)';
    case 'AGENT_B': return 'var(--violet)';
    case 'AGENT_C': return 'var(--amber)';
    case 'AGENT_D': return 'var(--emerald)';
    case 'TRADE': return 'var(--emerald)';
    case 'NEWS': return 'var(--amber)';
    case 'EMERGENCY': return 'var(--red)';
    case 'CONSENSUS': return 'var(--amber)';
    case 'PIPELINE': return 'var(--cyan)';
    case 'MIND': return 'var(--violet)';
    case 'SYNC': return 'var(--mid)';
    case 'TICK': return 'var(--dim)';
    default: return 'var(--dim)';
  }
};

export default function IntelligenceLog({ logs }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current) containerRef.current.scrollTop = 0;
  }, [logs]);

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden', background: 'rgba(5, 7, 12, 0.8)' }}>
      <div className="section-header" style={{ padding: '8px 16px', background: 'rgba(255,255,255,0.02)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className="pulse" style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--violet)', boxShadow: '0 0 10px var(--violet)' }} />
          <span className="fw-900 uppercase ls-wider" style={{ fontSize: '0.65rem' }}>Intelligence Stream</span>
        </div>
        <span className="font-mono c-dim" style={{ fontSize: '0.55rem' }}>{logs.length} EVTS</span>
      </div>
      
      <div 
        ref={containerRef}
        className="scrollbar-hide"
        style={{ padding: '12px', overflowY: 'auto', flex: 1, minHeight: 0 }}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          {logs.map((log) => {
            const isTrade = log.tag?.toUpperCase() === 'TRADE';
            const isNews = log.tag?.toUpperCase() === 'NEWS';
            const color = getTagColor(log.tag);
            
            return (
              <motion.div 
                key={log.id}
                initial={{ opacity: 0, height: 0, x: -5 }} animate={{ opacity: 1, height: 'auto', x: 0 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                style={{ 
                  display: 'flex', gap: '10px', fontSize: '0.6rem', padding: '3px 0', 
                  borderBottom: '1px solid rgba(255,255,255,0.02)',
                  fontFamily: '"JetBrains Mono", monospace'
                }}
              >
                <span className="c-dim" style={{ opacity: 0.4 }}>{log.ts}</span>
                <span className="fw-900" style={{ color, minWidth: '45px', letterSpacing: '0.1em' }}>{log.tag}</span>
                <span style={{ 
                  flex: 1, color: isTrade ? 'var(--emerald)' : isNews ? 'var(--top)' : 'var(--mid)',
                  fontWeight: (isTrade || isNews) ? '900' : 'normal',
                  textShadow: isTrade ? '0 0 8px rgba(0,255,170,0.2)' : 'none'
                }}>
                  {log.msg}
                </span>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {logs.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.3, fontSize: '0.6rem', fontStyle: 'italic', letterSpacing: '0.12em', paddingTop: '40px' }}>
            Waiting for matrix pulse...
          </div>
        )}
      </div>
    </div>
  );
}
