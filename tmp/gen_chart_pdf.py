from fpdf import FPDF
import os

class SovereignPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(20, 20, 100)
        self.cell(0, 10, 'Sovereign Matrix Neural Architecture Audit (V8.0)', border=False, ln=True, align='C')
        self.set_font('helvetica', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'Total Unification Blueprint - 250+ Neural Components', border=False, ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | Confidential Institutional Property', align='C')

def generate_pdf(output_path):
    pdf = SovereignPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # Header for the table
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_fill_color(220, 230, 241)
    
    col_widths = [45, 35, 45, 140]
    headers = ['Component', 'Category', 'Discipline', 'Role in the Unification']
    
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 10, headers[i], border=1, fill=True, align='C')
    pdf.ln()

    # Data content
    data = [
        ["Agent A (Oracle)", "Master Agent", "World Observation", "Ingests News, Sentiment, and Macro-Thematics live from the global web."],
        ["Agent B (Swarm)", "Master Agent", "Consensus Gate", "Orchestrates multi-agent debates to validate trade signals before firing."],
        ["Agent C (Imperial)", "Master Agent", "Execution", "Institutional order routing (IBKR/MT5) with aggressive limit logic."],
        ["Agent D (Learning)", "Master Agent", "Continuous Growth", "Neural growth engine; learns expectancy matrices from every trade outcome."],
        ["Agent E (Security)", "Master Agent", "Risk Defense", "Hard sector-correlation gate; prevents portfolio over-exposure."],
        ["Agent J (Ghost)", "Mind", "Resilience", "Self-healing mind; handles service recovery and infrastructure heartbeats."],
        ["Dhatu Oracle", "Organ", "Global Omniscience", "6-vertical synthesis of Oil, Geopolitics, and Macro causation graphs."],
        ["Mind Ultrathink", "Mind", "Deep Reasoning", "Supreme Court logic; performs final verification of consensus vs world context."],
        ["Swarm Predictor", "Organ", "Forecasting", "Simulates 30 rounds of persona-based debate to forecast market paths."],
        ["Intelligence Bus", "Organ", "Nervous System", "The pub/sub spine connecting every agent; ensures 0ms knowledge skew."],
        ["Chroma Memory", "Organ", "Vector Storage", "Long-term recall of past regimes using phrase-vector embedding."],
        ["Agent I (System)", "Mind", "Low-Level OS", "Certified command gate; handles port recovery and system scent control."],
        ["Trading Brain", "Organ", "Central Heart", "Centralized event loop resolving all agent inputs into single actions."],
        ["Data Pipeline", "Organ", "Circulatory", "Low-latency artery for tick-data and candle-batch propagation."],
        ["Mind Evolution", "Mind", "Mastery", "Leveling system that scales risk budget as system intelligence grows."],
        ["Mind Observer", "Mind", "Surveillance", "Tracks the behavioral 'scent' of every agent to detect logic decay."],
        ["Wisdom", "Mind", "Soul", "Permanent registry of the Sovereign Charter and past hard-won lessons."],
        ["DMS Shield", "Organ", "Risk Firewall", "Drawdown management; locks liquidity during high-chaos regimes."],
        ["QuestDB Adapter", "Organ", "HFT Storage", "Massive time-series storage for million-row backtesting and analysis."],
        ["Session Restorer", "Mind", "Continuity", "Ensures state persistence and logic recovery after system reboots."],
        ["API Server", "Organ", "Interface", "Broadcasts local events to the Sovereign Dashboard via WebSockets."],
        ["Vault", "Safe", "Cryptography", "Protected storage for API keys and restricted institutional credentials."],
        ["Diagnostic Tracker", "Mind", "Health Monitoring", "Generates real-time telemetry on every agent's latency and accuracy."],
        ["Correlation Guard", "Organ", "Defense", "Prevents simultaneous exposure across sector-linked ticker sets."]
    ]

    pdf.set_font('helvetica', '', 9)
    for row in data:
        # Check if we need a new page
        if pdf.get_y() > 180:
            pdf.add_page()
            # Re-add header
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_fill_color(220, 230, 241)
            for i in range(len(headers)):
                pdf.cell(col_widths[i], 10, headers[i], border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font('helvetica', '', 9)

        # Calculate heights for multi-cell
        start_y = pdf.get_y()
        pdf.multi_cell(col_widths[0], 8, row[0], border=1, align='L')
        end_y_0 = pdf.get_y()
        
        pdf.set_xy(pdf.get_x() + col_widths[0], start_y)
        pdf.multi_cell(col_widths[1], 8, row[1], border=1, align='L')
        end_y_1 = pdf.get_y()
        
        pdf.set_xy(pdf.get_x() + col_widths[0] + col_widths[1], start_y)
        pdf.multi_cell(col_widths[2], 8, row[2], border=1, align='L')
        end_y_2 = pdf.get_y()
        
        pdf.set_xy(pdf.get_x() + col_widths[0] + col_widths[1] + col_widths[2], start_y)
        pdf.multi_cell(col_widths[3], 8, row[3], border=1, align='L')
        end_y_3 = pdf.get_y()
        
        final_y = max(end_y_0, end_y_1, end_y_2, end_y_3)
        # Move to next row
        pdf.set_y(final_y)

    pdf.output(output_path)
    print(f"Successfully generated audit chart: {output_path}")

if __name__ == "__main__":
    generate_pdf('sovereign_matrix_chart.pdf')
