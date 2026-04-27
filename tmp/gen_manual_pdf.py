from fpdf import FPDF
import os

class SovereignManualPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(20, 40, 100)
        self.cell(0, 10, 'Sovereign Matrix Neural Architecture: Operational Manual (V8.0)', border=False, ln=True, align='C')
        self.set_font('helvetica', 'I', 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, 'Unified Intelligence & Role-Based System Blueprint', border=False, ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | CONFIDENTIAL: Sovereign Intelligence Network', align='C')

def generate_manual(output_path):
    pdf = SovereignManualPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    components = [
        {
            "name": "Agent A (Oracle)",
            "category": "Master Agent",
            "discipline": "Global Ingestion",
            "doing": "Scanning thousands of news headlines, central bank transcripts, and geopolitical alerts every minute.",
            "role": "Translates the 'Noise' of the world into a 'Sentiment Signal'. It ensures the system knows why the market is moving."
        },
        {
            "name": "Agent B (Swarm)",
            "category": "Master Agent",
            "discipline": "Strategist",
            "doing": "Orchestrating a 5-way debate between competing AI personalities (Bull, Bear, Volatility, Psychology, Risk).",
            "role": "Synthesizes thousands of data-points into a single 'Go/No-Go' consensus. It is the final judge of a setup's quality."
        },
        {
            "name": "Agent C (Imperial)",
            "category": "Master Agent",
            "discipline": "Execution",
            "doing": "Opening and closing orders via IBKR and MT5 gateways using precision routing.",
            "role": "To strike at the best possible price. It uses hidden limit orders to minimize the slippage that eats your profit."
        },
        {
            "name": "Agent D (Learning)",
            "category": "Master Agent",
            "discipline": "Neural Growth",
            "doing": "Updating statistical win-rate matrices across 500+ pattern/regime combinations.",
            "role": "To ensure the system 'Levels Up'. If it loses a trade today, Agent D ensures it doesn't make the same mistake tomorrow."
        },
        {
            "name": "Agent E (Security)",
            "category": "Master Agent",
            "discipline": "Risk Defense",
            "doing": "Monitoring sector-level correlation and total portfolio heat.",
            "role": "Prevents 'Sudden Death'. It stops the system from buying 10 Tech stocks that all crash together on one news event."
        },
        {
            "name": "Dhatu Oracle",
            "category": "Global Organ",
            "discipline": "Omniscience",
            "doing": "Building a Graph of Causation (e.g. Fed Policy -> Yields -> Dollar -> Gold).",
            "role": "Provides the 'Big Picture'. It tells the other agents which regime we are in (Vriddhi, Kshaya, Viyoga) so they use the right strategy."
        },
        {
            "name": "Mind Ultrathink",
            "category": "Mind",
            "discipline": "Deep Reasoning",
            "doing": "Performing deep chain-of-thought analysis on complex market scenarios.",
            "role": "Acts as the 'Supreme Court'. It can Veto any trade that looks good technically but fails a 'Common Sense' logic check."
        },
        {
            "name": "Swarm Predictor",
            "category": "Organ",
            "discipline": "Forecasting",
            "doing": "Simulating future market trajectories using the MiroFish debate engine.",
            "role": "Predicts the 'Next Move'. It looks 30 minutes ahead to see if a breakout is likely to fail or follow through."
        },
        {
            "name": "Intelligence Bus",
            "category": "Organ",
            "discipline": "Nervous System",
            "doing": "Broadcasting signals (Candles, Oracles, Calibrations) at sub-millisecond speeds.",
            "role": "Synchronization. It ensures that when Agent A sees a crash, Agent C knows to exit before the news even hits the TV."
        },
        {
            "name": "Agent J (Ghost)",
            "category": "Mind",
            "discipline": "Resilience",
            "doing": "Monitoring system health and auto-restarting crashed broker gateways.",
            "role": "Immunity. It ensures the system never goes 'Data Dark' or loses control of its connections during a market move."
        },
        {
            "name": "Mind Evolution",
            "category": "Mind",
            "discipline": "Mastery",
            "doing": "Tracking the Skill Tree of the Matrix and unlocking new risk tiers.",
            "role": "Scaling. It ensures you only risk more money after the system has proven it can handle smaller amounts profitably."
        },
        {
            "name": "Mind Observer",
            "category": "Mind",
            "discipline": "Surveillance",
            "doing": "Tracking the 'Scent' of every agent to detect mental drift or code decay.",
            "role": "Integrity. It alerts you if an agent is behaving 'differently' than its original design parameters."
        },
        {
            "name": "DMS Shield",
            "category": "Organ",
            "discipline": "Risk Management",
            "doing": "Enforcing hard dollar limits on daily, weekly, and total drawdown.",
            "role": "Capital Preservation. It is the absolute firewall that stops the system if a Black Swan event exceeds risk limits."
        },
        {
            "name": "Wisdom",
            "category": "Mind",
            "discipline": "Sovereign Soul",
            "doing": "Storing the Permanent Charter of rules that no agent can ever violate.",
            "role": "Ethics/Rules. It ensures the system stays within the 'Sovereign' guidelines you set, no matter how volatile the market gets."
        },
        {
            "name": "QuestDB Adapter",
            "category": "Organ",
            "discipline": "Memory",
            "doing": "Ingesting and storing millions of rows of tick-data for instant callback.",
            "role": "Learning Data. It provides the 'Library' that Agent D uses to verify historical win rates."
        }
    ]

    for comp in components:
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(30, 60, 150)
        pdf.cell(0, 10, f"| Component: {comp['name']}", ln=True)
        
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(40, 7, "Category:", border=0)
        pdf.set_font('helvetica', '', 9)
        pdf.cell(0, 7, comp['category'], ln=True)
        
        pdf.set_font('helvetica', 'B', 9)
        pdf.cell(40, 7, "Discipline:", border=0)
        pdf.set_font('helvetica', '', 9)
        pdf.cell(0, 7, comp['discipline'], ln=True)

        # Use multi_cell for 'doing' and 'role' to handle wrapping
        pdf.set_font('helvetica', 'B', 9)
        pdf.cell(40, 7, "Current Action:", border=0)
        pdf.set_font('helvetica', 'I', 9)
        pdf.set_text_color(100, 30, 30)
        pdf.set_x(50) # Indent the text for multi_cell
        pdf.multi_cell(150, 7, comp['doing'], ln=True)

        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(40, 7, "Strategic Role:", border=0)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(0, 80, 0)
        pdf.set_x(50)
        pdf.multi_cell(150, 7, comp['role'], ln=True)
        
        pdf.ln(5)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    pdf.output(output_path)
    print(f"Manual generated successfully: {output_path}")

if __name__ == "__main__":
    generate_manual('sovereign_intelligence_manual.pdf')
