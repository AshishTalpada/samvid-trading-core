import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

/** 📊 Trading Chart v1.0-beta-beta (Institutional Grade)
 *  High-performance candlestick visualization with robust ISO-to-Unix normalization.
 */

const TradingChart = ({ symbol = 'SPY', data = [] }) => {
  const chartContainerRef = useRef();
  const chartRef = useRef();
  const seriesRef = useRef();
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // ── INITIALIZE CHART ──
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
      },
      width: chartContainerRef.current.clientWidth || 800,
      height: chartContainerRef.current.clientHeight || 480,
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
      }
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#00ffaa',
      downColor: '#ff3366',
      borderVisible: false,
      wickUpColor: '#00ffaa',
      wickDownColor: '#ff3366',
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({ 
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !data || !Array.isArray(data) || data.length === 0) {
      setHasData(false);
      return;
    }

    try {
      // ── ROBUST DATA NORMALIZATION ──
      const formattedData = data
        .map(item => {
          let t = item.time;
          if (typeof t === 'string') {
            // Convert ISO "2026-04-07T15:00:00-04:00" to Unix (seconds)
            t = Math.floor(new Date(t).getTime() / 1000);
          }
          return {
            time: t,
            open: parseFloat(item.open),
            high: parseFloat(item.high),
            low: parseFloat(item.low),
            close: parseFloat(item.close)
          };
        })
        .filter(item => !isNaN(item.time) && !isNaN(item.open))
        .sort((a, b) => a.time - b.time);

      // Ensure unique timestamps (lightweight-charts requirement)
      const uniqueData = [];
      const seenTimes = new Set();
      for (const d of formattedData) {
        if (!seenTimes.has(d.time)) {
          uniqueData.push(d);
          seenTimes.add(d.time);
        }
      }

      if (uniqueData.length > 0) {
        seriesRef.current.setData(uniqueData);
        setHasData(true);
      }
    } catch (err) {
      console.error("🌌 [Chart Engine] Convergence Error:", err);
    }
  }, [data]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'rgba(5,7,12,0.5)', borderRadius: '8px', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: '12px', left: '16px', zIndex: 10, display: 'flex', gap: '8px', alignItems: 'center' }}>
        <span className="fw-900 c-top font-outfit" style={{ fontSize: '1rem', letterSpacing: '0.05em' }}>{symbol} / USD</span>
        <span className="badge-sovereign c-cyan" style={{ fontSize: '0.5rem' }}>REAL-TIME FEED</span>
      </div>
      
      {!hasData && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 5, background: 'rgba(5,7,12,0.8)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
             <div className="pulse" style={{ width: '40px', height: '40px', border: '2px solid var(--violet)', borderRadius: '50%', borderTopColor: 'transparent', animation: 'spin 1s linear infinite' }} />
             <span className="fw-900 c-dim ls-wider uppercase" style={{ fontSize: '0.6rem' }}>Synchronizing Market Data...</span>
          </div>
        </div>
      )}

      <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
      
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default TradingChart;
