import React from 'react';

/** 🏛️ Sovereign Layout System (Institutional Grid - Vanilla CSS) */

export default function MainLayout({ sidebarL, center, panelR }) {
  return (
    <div className="layout-root">
      
      {/* 🛰️ LEFT NERVE CENTER (Fixed) */}
      <aside className="layout-sidebar-l">
        {sidebarL}
      </aside>

      {/* 🔭 CENTRAL OBSERVATORY (Flexible Grid) */}
      <main className="layout-center">
        {center}
      </main>

      {/* 📊 ANALYTICS PANEL (Fixed) */}
      <aside className="layout-panel-r">
        {panelR}
      </aside>

      <style>{`
        /* 📱 Standard Breakpoints for Institutional Displays */
        @media (max-width: 1280px) {
          :root { --panel-r-w: 260px; --sidebar-w: 220px; }
        }

        @media (max-width: 1024px) {
          .layout-panel-r { display: none; }
          :root { --sidebar-w: 200px; }
        }

        @media (max-width: 850px) {
          .layout-root { flex-direction: column; overflow-y: auto; overflow-x: hidden; }
          .layout-sidebar-l, .layout-center, .layout-panel-r { width: 100% !important; height: auto !important; flex-grow: 1; flex-shrink: 0; }
        }

        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
    </div>
  );
}
