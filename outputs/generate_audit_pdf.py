"""
Trading System Audit Report - PDF Generator
Generates a comprehensive step-by-step remediation guide.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import (
    HexColor, black, white, red, darkred, darkgreen,
    orange, gray, darkgray, lightgrey
)
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem
)
from reportlab.platypus.tableofcontents import TableOfContents
from datetime import datetime
import os

# ── Colour palette ──────────────────────────────────────────────
CLR_PRIMARY    = HexColor("#1a1a2e")
CLR_ACCENT     = HexColor("#e94560")
CLR_ACCENT2    = HexColor("#0f3460")
CLR_SUCCESS    = HexColor("#16a34a")
CLR_WARNING    = HexColor("#ea580c")
CLR_DANGER     = HexColor("#dc2626")
CLR_INFO       = HexColor("#2563eb")
CLR_BG_LIGHT   = HexColor("#f8fafc")
CLR_BG_HEADER  = HexColor("#1e293b")
CLR_BG_ROW_ALT = HexColor("#f1f5f9")
CLR_BORDER     = HexColor("#cbd5e1")
CLR_TEXT       = HexColor("#1e293b")
CLR_TEXT_LIGHT = HexColor("#64748b")
CLR_GOLD       = HexColor("#f59e0b")

# ── Styles ──────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def make_style(name, parent="Normal", **kw):
    base = styles[parent]
    return ParagraphStyle(name, parent=base, **kw)

S_TITLE = make_style("S_TITLE", "Title",
    fontSize=28, leading=34, textColor=CLR_PRIMARY,
    spaceAfter=6, alignment=TA_CENTER, fontName="Helvetica-Bold")

S_SUBTITLE = make_style("S_SUBTITLE",
    fontSize=14, leading=18, textColor=CLR_TEXT_LIGHT,
    spaceAfter=20, alignment=TA_CENTER)

S_H1 = make_style("S_H1", "Heading1",
    fontSize=20, leading=26, textColor=CLR_PRIMARY,
    spaceBefore=24, spaceAfter=10, fontName="Helvetica-Bold")

S_H2 = make_style("S_H2", "Heading2",
    fontSize=16, leading=20, textColor=CLR_ACCENT2,
    spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold")

S_H3 = make_style("S_H3", "Heading3",
    fontSize=13, leading=17, textColor=CLR_TEXT,
    spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold")

S_BODY = make_style("S_BODY",
    fontSize=10, leading=14, textColor=CLR_TEXT,
    spaceAfter=6, alignment=TA_JUSTIFY)

S_BODY_SMALL = make_style("S_BODY_SMALL",
    fontSize=9, leading=12, textColor=CLR_TEXT, spaceAfter=4)

S_CODE = make_style("S_CODE",
    fontSize=8.5, leading=11, fontName="Courier",
    textColor=HexColor("#1e293b"), backColor=HexColor("#f1f5f9"),
    leftIndent=12, rightIndent=12, spaceBefore=4, spaceAfter=4,
    borderPadding=(6, 6, 6, 6))

S_BULLET = make_style("S_BULLET",
    fontSize=10, leading=14, textColor=CLR_TEXT,
    leftIndent=24, bulletIndent=12, spaceAfter=3)

S_BULLET_SUB = make_style("S_BULLET_SUB",
    fontSize=9.5, leading=13, textColor=CLR_TEXT,
    leftIndent=42, bulletIndent=30, spaceAfter=2)

S_TAG_CRITICAL = make_style("S_TAG_CRITICAL",
    fontSize=9, fontName="Helvetica-Bold", textColor=white,
    backColor=CLR_DANGER, alignment=TA_CENTER)

S_TAG_HIGH = make_style("S_TAG_HIGH",
    fontSize=9, fontName="Helvetica-Bold", textColor=white,
    backColor=CLR_WARNING, alignment=TA_CENTER)

S_TAG_MEDIUM = make_style("S_TAG_MEDIUM",
    fontSize=9, fontName="Helvetica-Bold", textColor=white,
    backColor=CLR_INFO, alignment=TA_CENTER)

S_TAG_LOW = make_style("S_TAG_LOW",
    fontSize=9, fontName="Helvetica-Bold", textColor=white,
    backColor=CLR_TEXT_LIGHT, alignment=TA_CENTER)

S_TIP = make_style("S_TIP",
    fontSize=9.5, leading=13, textColor=HexColor("#065f46"),
    backColor=HexColor("#ecfdf5"), leftIndent=12, rightIndent=12,
    spaceBefore=6, spaceAfter=6, borderPadding=(8, 8, 8, 8))

S_WARNING_BOX = make_style("S_WARNING_BOX",
    fontSize=9.5, leading=13, textColor=HexColor("#9a3412"),
    backColor=HexColor("#fff7ed"), leftIndent=12, rightIndent=12,
    spaceBefore=6, spaceAfter=6, borderPadding=(8, 8, 8, 8))

S_DANGER_BOX = make_style("S_DANGER_BOX",
    fontSize=9.5, leading=13, textColor=HexColor("#991b1b"),
    backColor=HexColor("#fef2f2"), leftIndent=12, rightIndent=12,
    spaceBefore=6, spaceAfter=6, borderPadding=(8, 8, 8, 8))

S_TABLE_HEADER = make_style("S_TABLE_HEADER",
    fontSize=9, fontName="Helvetica-Bold", textColor=white,
    alignment=TA_CENTER)

S_TABLE_CELL = make_style("S_TABLE_CELL",
    fontSize=8.5, leading=11, textColor=CLR_TEXT)

S_TABLE_CELL_C = make_style("S_TABLE_CELL_C",
    fontSize=8.5, leading=11, textColor=CLR_TEXT, alignment=TA_CENTER)

S_FOOTER = make_style("S_FOOTER",
    fontSize=7, textColor=CLR_TEXT_LIGHT, alignment=TA_CENTER)

# ── Helper functions ────────────────────────────────────────────

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=CLR_BORDER,
                      spaceBefore=8, spaceAfter=8)

def sp(pts=6):
    return Spacer(1, pts)

def bullet(text, style=S_BULLET):
    return Paragraph(f"<bullet>&bull;</bullet> {text}", style)

def sub_bullet(text):
    return Paragraph(f"<bullet>-</bullet> {text}", S_BULLET_SUB)

def code_block(text):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, S_CODE)

def severity_tag(level):
    mapping = {
        "CRITICAL": S_TAG_CRITICAL,
        "HIGH": S_TAG_HIGH,
        "MEDIUM": S_TAG_MEDIUM,
        "LOW": S_TAG_LOW,
    }
    return Paragraph(level, mapping.get(level, S_TAG_LOW))

def tip_box(text):
    return Paragraph(f"<b>TIP:</b> {text}", S_TIP)

def warning_box(text):
    return Paragraph(f"<b>WARNING:</b> {text}", S_WARNING_BOX)

def danger_box(text):
    return Paragraph(f"<b>DANGER:</b> {text}", S_DANGER_BOX)

def make_table(headers, rows, col_widths=None):
    """Build a styled table with header row."""
    header_cells = [Paragraph(h, S_TABLE_HEADER) for h in headers]
    data = [header_cells]
    for row in rows:
        data.append([
            Paragraph(str(c), S_TABLE_CELL) if i == 0 or i == len(row)-1
            else Paragraph(str(c), S_TABLE_CELL_C)
            for i, c in enumerate(row)
        ])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), CLR_BG_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, CLR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), CLR_BG_ROW_ALT))
    t.setStyle(TableStyle(style_cmds))
    return t

def step_header(num, title):
    return Paragraph(
        f'<font color="{CLR_ACCENT.hexval()}">STEP {num}</font>  '
        f'<font color="{CLR_PRIMARY.hexval()}">{title}</font>',
        S_H3
    )

def phase_header(num, title, description):
    elements = []
    elements.append(Paragraph(
        f'<font color="{CLR_ACCENT.hexval()}">PHASE {num}:</font> {title}', S_H2))
    elements.append(Paragraph(description, S_BODY))
    elements.append(hr())
    return elements

# ── Page template callbacks ─────────────────────────────────────

def on_first_page(canvas, doc):
    canvas.saveState()
    # Top accent bar
    canvas.setFillColor(CLR_PRIMARY)
    canvas.rect(0, A4[1] - 4*mm, A4[0], 4*mm, fill=True, stroke=False)
    # Bottom accent bar
    canvas.setFillColor(CLR_ACCENT)
    canvas.rect(0, 0, A4[0], 3*mm, fill=True, stroke=False)
    canvas.restoreState()

def on_later_pages(canvas, doc):
    canvas.saveState()
    # Top line
    canvas.setStrokeColor(CLR_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(50, A4[1] - 30, A4[0] - 50, A4[1] - 30)
    # Header text
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(CLR_TEXT_LIGHT)
    canvas.drawString(50, A4[1] - 25, "Trading System Audit Report | Confidential")
    canvas.drawRightString(A4[0] - 50, A4[1] - 25, f"Page {doc.page}")
    # Bottom line
    canvas.line(50, 30, A4[0] - 50, 30)
    canvas.drawCentredString(A4[0]/2, 18,
        f"Generated {datetime.now().strftime('%Y-%m-%d')} | System Beta v1.0")
    # Bottom accent
    canvas.setFillColor(CLR_ACCENT)
    canvas.rect(0, 0, A4[0], 2*mm, fill=True, stroke=False)
    canvas.restoreState()


# ── BUILD THE DOCUMENT ──────────────────────────────────────────

def build_pdf():
    output_path = os.path.join(os.path.dirname(__file__),
                               "TradingSystem_Audit_Report.pdf")
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=55, bottomMargin=50,
        title="Trading System - Complete Audit & Remediation Guide",
        author="System Audit",
    )
    story = []
    W = A4[0] - 100  # usable width

    # ════════════════════════════════════════════════════════════
    # COVER PAGE
    # ════════════════════════════════════════════════════════════
    story.append(sp(80))
    story.append(Paragraph("TRADING SYSTEM", S_TITLE))
    story.append(Paragraph("Complete Audit &amp; Remediation Guide", make_style(
        "cover_sub", fontSize=18, leading=22, textColor=CLR_ACCENT,
        alignment=TA_CENTER, spaceAfter=12)))
    story.append(hr())
    story.append(Paragraph("System Beta v1.0 | Confidential", S_SUBTITLE))
    story.append(sp(30))

    # Summary stats table
    summary_data = [
        ["Total Issues Found", "130+"],
        ["Critical Issues", "7"],
        ["High Severity", "12"],
        ["Medium Severity", "15+"],
        ["Low Severity", "10+"],
        ["Remediation Steps", "30"],
        ["Enhancement Suggestions", "20"],
    ]
    summary_table = Table(
        [[Paragraph(r[0], S_BODY), Paragraph(f"<b>{r[1]}</b>", make_style(
            "sv", fontSize=11, fontName="Helvetica-Bold", textColor=CLR_ACCENT,
            alignment=TA_CENTER))] for r in summary_data],
        colWidths=[3.2*inch, 1.5*inch]
    )
    summary_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, CLR_BORDER),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("BACKGROUND", (0,0), (0,-1), CLR_BG_LIGHT),
    ]))
    story.append(summary_table)
    story.append(sp(30))

    story.append(Paragraph(f"Report Date: {datetime.now().strftime('%B %d, %Y')}",
                           make_style("dt", fontSize=10, textColor=CLR_TEXT_LIGHT,
                                      alignment=TA_CENTER)))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("TABLE OF CONTENTS", S_H1))
    story.append(hr())
    toc_items = [
        ("Part A", "Complete Issue Registry", "3"),
        ("  A1", "Critical Issues (7)", "3"),
        ("  A2", "High Severity Issues (12)", "5"),
        ("  A3", "Medium Severity Issues (15+)", "7"),
        ("  A4", "Low Severity Issues (10+)", "9"),
        ("Part B", "Step-by-Step Remediation Plan", "11"),
        ("  Phase 1", "Stop the Bleeding - Critical Fixes (Steps 1-6)", "11"),
        ("  Phase 2", "Security Hardening (Steps 7-11)", "15"),
        ("  Phase 3", "Race Conditions & Async Fixes (Steps 12-14)", "18"),
        ("  Phase 4", "Logic Bug Fixes (Steps 15-18)", "20"),
        ("  Phase 5", "Stub Implementations (Step 19)", "22"),
        ("  Phase 6", "Performance Optimization (Steps 20-22)", "23"),
        ("  Phase 7", "Configuration Cleanup (Steps 23-24)", "24"),
        ("  Phase 8", "Test Coverage (Steps 25-27)", "25"),
        ("  Phase 9", "Build & Deployment (Steps 28-30)", "27"),
        ("Part C", "Enhancement Suggestions", "28"),
        ("  C1", "Architecture Enhancements", "28"),
        ("  C2", "AI/ML Intelligence Upgrades", "29"),
        ("  C3", "Risk Management Enhancements", "30"),
        ("  C4", "Data & Execution Improvements", "31"),
        ("  C5", "Monitoring & Observability", "32"),
        ("Part D", "Execution Timeline & Priority Matrix", "33"),
    ]
    toc_data = []
    for section, title, page in toc_items:
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" if section.startswith("  ") else ""
        sec = section.strip()
        toc_data.append([
            Paragraph(f"{indent}<b>{sec}</b>", S_TABLE_CELL),
            Paragraph(title, S_TABLE_CELL),
            Paragraph(page, S_TABLE_CELL_C),
        ])
    toc_table = Table(toc_data, colWidths=[1.2*inch, 4*inch, 0.6*inch])
    toc_table.setStyle(TableStyle([
        ("LINEBELOW", (0,0), (-1,-1), 0.3, CLR_BORDER),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PART A: COMPLETE ISSUE REGISTRY
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("PART A: COMPLETE ISSUE REGISTRY", S_H1))
    story.append(Paragraph(
        "Every issue discovered during the audit, organized by severity. "
        "Each issue includes the file location, description, and impact.",
        S_BODY))
    story.append(hr())

    # ── A1: CRITICAL ────────────────────────────────────────────
    story.append(Paragraph("A1. CRITICAL ISSUES", S_H2))
    story.append(danger_box(
        "These issues will cause runtime crashes, data loss, or financial risk. "
        "The system should NOT trade live until all critical issues are resolved."))
    story.append(sp(6))

    critical_issues = [
        ("C1", "Python Version Mismatch",
         "Config declares Python 3.11.9 but system runs 3.14.3",
         ".python-version, pyproject.toml, requirements.txt, system_config.py",
         "All four config files specify Python 3.11.9 but the actual runtime is 3.14.3. "
         "This causes: (a) encoding errors visible as UTF-16 BOM mojibake in all log files, "
         "(b) dependency incompatibilities with packages pinned to 3.11, "
         "(c) test failures due to changed stdlib behavior in 3.14. "
         "Tests currently produce unreadable output."),

        ("C2", "Infinite Recursion in Dead Man's Switch",
         "DMS emergency flatten calls itself with no depth limit",
         "src/dms.py : lines 211-214",
         "execute_emergency_flatten() recursively calls itself after IBKR reconnects. "
         "Under network instability (connection flapping), this hits Python's recursion limit "
         "and crashes with RecursionError. This is the EMERGENCY POSITION FLATTENING code - "
         "if it crashes, open positions remain unprotected during broker outages."),

        ("C3", "SQL Injection Vulnerabilities (2 locations)",
         "F-string interpolation in SQL statements",
         "src/agent_c.py : line 121-123, src/questdb_adapter.py : line 322",
         "agent_c.py uses f-string in ATTACH DATABASE command. questdb_adapter.py uses "
         "f-string in ALTER TABLE DROP PARTITION. Both allow injection if input is "
         "crafted. While current inputs are internal, any future change that passes "
         "user-influenced data to these paths creates an exploitable vulnerability."),

        ("C4", "Bare Excepts Swallowing Trade-Critical Errors (6+ locations)",
         "Exception handlers that catch-and-ignore errors in critical paths",
         "src/agent_c.py:112, src/data_pipeline.py:258+321, src/dms.py:101, "
         "src/swarm_predictor.py:309+394, src/questdb_adapter.py:124",
         "Trade execution errors in agent_c are silently ignored with 'except: pass'. "
         "Data pipeline returns None on fetch failure with no alert. DMS swallows telegram "
         "failures (so nobody knows positions are at risk). Swarm predictor returns stale "
         "fallback data as if fresh. QuestDB worker thread silently drops connection errors. "
         "Combined effect: the system can be silently broken while appearing healthy."),

        ("C5", "Division by Zero / None Dereference (4 locations)",
         "Missing zero-checks before division operations",
         "src/exit_intelligence.py:56, src/agent_c.py:142, "
         "src/mind_ultrathink.py:85, src/coordinator.py:246",
         "exit_intelligence computes slippage without checking qty==0. agent_c divides "
         "wins/total without checking total==0. mind_ultrathink divides by "
         "len(resonance_results) which can be empty. coordinator uses 'or 0' fallback "
         "that breaks when entry_price is legitimately 0."),

        ("C6", "Polars API Method Does Not Exist",
         ".rolling_min() is not a valid Polars method",
         "src/agent_a.py : line 278",
         "Code calls df['low'][-30:].rolling_min() but Polars does not have a rolling_min() "
         "method on Series. This will raise AttributeError every time the head-and-shoulders "
         "pattern detector runs, meaning this pattern is NEVER detected."),

        ("C7", "Test Fixtures Incompatible with Code",
         "Tests crash before running due to signature mismatches",
         "tests/test_trading_brain.py : lines 9-27",
         "Fixture passes db_path= keyword but TradingBrain.__init__ expects db_conn=. "
         "Also double-mocks sqlite3.connect (patched globally AND passed as argument). "
         "AsyncMock for _detect_regime() is not configured, so it returns 'UNKNOWN' "
         "instead of expected 'BULL'. All brain tests are currently broken."),
    ]

    for cid, title, summary, location, detail in critical_issues:
        story.append(KeepTogether([
            Paragraph(f'<font color="{CLR_DANGER.hexval()}">[{cid}]</font> '
                      f'<b>{title}</b>', S_H3),
            Paragraph(f'<i>{summary}</i>', S_BODY_SMALL),
            Paragraph(f'<font color="{CLR_TEXT_LIGHT.hexval()}">Location: {location}</font>',
                      S_BODY_SMALL),
            sp(3),
            Paragraph(detail, S_BODY),
            sp(6),
        ]))

    story.append(PageBreak())

    # ── A2: HIGH SEVERITY ───────────────────────────────────────
    story.append(Paragraph("A2. HIGH SEVERITY ISSUES", S_H2))
    story.append(warning_box(
        "Security vulnerabilities, race conditions, and data integrity risks. "
        "These won't crash immediately but will cause incorrect behavior or expose the system."))
    story.append(sp(6))

    high_issues = [
        ("H1", "Hardcoded Secrets in Source Code",
         "session_restorer.py:27 hardcodes secret_key='SETO_ABSOLUTE_V6'. "
         "questdb_adapter.py:30 has default password='quest'. "
         "mind_system.py:96 hardcodes 'C:\\\\Jts' path. "
         "system_config.py:49-51 stores API key names in plain text."),
        ("H2", "API Keys Leaked in URLs and Logs",
         "data_pipeline.py:276 embeds Finnhub API key directly in URL query string: "
         "f'...&amp;token={self.finnhub_key}'. This appears in error traces, log files, "
         "and network monitoring tools."),
        ("H3", "Race Conditions on Shared Mutable State (4 locations)",
         "coordinator.py:40-43 accesses _pending_vets set without locks. "
         "dms.py:52-66 modifies alert_sent/flatten_executed without locks. "
         "intelligence_bus.py:70-72 accesses subscriber dicts without locks. "
         "api_cache.py:107 races between emptiness check and min() call."),
        ("H4", "Pickle Deserialization Without Validation",
         "session_restorer.py:127 calls pickle.loads(data) with no structure validation. "
         "Corrupted pickle files cause crashes. Malicious pickle files enable arbitrary "
         "code execution."),
        ("H5", "Command Injection Risk (2 locations)",
         "mind_system.py:127 inserts path variable into shell command via f-string. "
         "mind_system.py:215 builds taskkill command with string interpolation. "
         "Crafted inputs could escape quotes and execute arbitrary commands."),
        ("H6", "Weak Caller Verification (Bypassable Security)",
         "agent_c_ibkr.py:176-179, 251-254, 130-133 uses inspect.currentframe() "
         "to verify callers. This is trivially bypassed by wrapping the function "
         "call. Provides false sense of security."),
        ("H7", "Docker Container Has No Resource Limits",
         "docker-compose.questdb.yml has no CPU/memory limits and no health check. "
         "QuestDB can consume all host resources. System has no way to detect if "
         "QuestDB is down."),
        ("H8", "Vault Fallback Returns Empty Strings Silently",
         "config.py:41 IBKR_ACCOUNT_ID = Vault.get('IBKR_ACCOUNT_ID', ''). If Vault "
         "fails, empty string propagates to IBKR API calls, causing silent failures "
         "or unintended behavior."),
        ("H9", "Float Conversion Without Validation",
         "config.py:104 STARTING_CAPITAL_CAD = float(Vault.get('TOTAL_CAPITAL', '500.0')). "
         "If Vault returns a non-numeric string, this crashes with ValueError at import time, "
         "bringing down the entire system."),
        ("H10", "Unvalidated JSON from External Sources",
         "intelligence_bus.py:195 calls json.loads(data.decode()) with no schema "
         "validation. workload_manager.py:44 loads JSON without structure checks. "
         "Missing keys raise KeyError at runtime."),
        ("H11", "WAL Files Never Cleaned Up",
         "data_pipeline.py:112-115 enables SQLite WAL mode but never cleans WAL files. "
         "Over time these can fill the disk, especially on a trading system running 24/5."),
        ("H12", "Fire-and-Forget Async Tasks",
         "ibkr_streamer.py:118 creates tasks with asyncio.create_task() but never "
         "tracks them. telegram_alerts.py:22 awaits HTTP post but ignores the result. "
         "Failed tasks are silently lost."),
    ]

    for hid, title, detail in high_issues:
        story.append(KeepTogether([
            Paragraph(f'<font color="{CLR_WARNING.hexval()}">[{hid}]</font> '
                      f'<b>{title}</b>', S_H3),
            Paragraph(detail, S_BODY),
            sp(4),
        ]))

    story.append(PageBreak())

    # ── A3: MEDIUM SEVERITY ─────────────────────────────────────
    story.append(Paragraph("A3. MEDIUM SEVERITY ISSUES", S_H2))
    story.append(sp(4))

    medium_issues = [
        ("M1", "Falling Wedge Logic Inverted",
         "agent_b.py:328-333 checks high_coef[0] >= low_coef[0] for convergence, "
         "but for a falling wedge the logic should be reversed."),
        ("M2", "Confidence Threshold Hardcoded, Ignores Config",
         "agent_a.py:922-933 uses hardcoded 60.0 instead of BELIEF_CAP from config."),
        ("M3", "Ghost Timer Uses Modulo on Time (Unreliable)",
         "mind_ghost.py:63-64 checks int(current_time) % 15 == 0. This fires once per "
         "second only when the condition is met, not every 15 seconds."),
        ("M4", "Coordinator Forces 5 Shares Without Cash Check",
         "coordinator.py:236-238 forces shares to 5 when confidence > 68% without "
         "checking if sufficient cash reserve exists."),
        ("M5", "DMS Contract Qualification Result Ignored",
         "dms.py:184 awaits qualifyContractsAsync() but discards the return value."),
        ("M6", "Stub Methods Returning Fake Data (7 locations)",
         "mind_observer.py always returns 'BULLISH'/'CLEAN'. mind_evolution.py returns "
         "static optimization values. mind_experiment.py shadow tests do nothing. "
         "agent_c.py evolution cycle is a no-op. System thinks it has AI intelligence "
         "but these are all hardcoded placeholders."),
        ("M7", "WebSocket Pushes Full State Every Second",
         "api_server.py:261-282 fetches 60 OHLCV bars for 3 symbols on every push. "
         "At 1 push/second this creates massive database load."),
        ("M8", "OHLCV Buffer Copies Full Arrays on Every Scan",
         "agent_a.py:46-68 update_from_df() copies entire arrays. No delta updates."),
        ("M9", "Semaphore Bottleneck Stalls Vetting",
         "coordinator.py:48 limits concurrent symbol vetting to 3. Can stall the "
         "entire system during high-activity periods."),
        ("M10", "Two Config Files With Overlapping Settings",
         "config.py and system_config.py have duplicate/conflicting settings. "
         "FTMO_DAILY_LIMIT in system_config.py conflicts with agent_c_mt5.py."),
        ("M11", "asyncio Queue Created Outside Event Loop",
         "questdb_adapter.py:42 creates asyncio.Queue in __init__. Fails if called "
         "before event loop exists."),
        ("M12", "IBKR Connection Brute Force Takes 75 Seconds",
         "ibkr_streamer.py:65-84 tries 150 host/client_id combos at 0.5s each."),
        ("M13", "Inconsistent Return Types in Data Pipeline",
         "data_pipeline.py fetch_ohlcv() returns Optional[DataFrame] but implicitly "
         "returns None in 5 different places. Callers don't consistently check."),
        ("M14", "String Format Bug in API Server",
         "api_server.py:283 has extra curly braces in f-string, creating malformed output."),
        ("M15", "Database Init Blocks Event Loop",
         "data_pipeline.py:106 _init_database() runs synchronously in __init__, "
         "blocking the async event loop during startup."),
    ]

    for mid, title, detail in medium_issues:
        story.append(KeepTogether([
            Paragraph(f'<font color="{CLR_INFO.hexval()}">[{mid}]</font> '
                      f'<b>{title}</b>', S_H3),
            Paragraph(detail, S_BODY),
            sp(3),
        ]))

    story.append(PageBreak())

    # ── A4: LOW SEVERITY ────────────────────────────────────────
    story.append(Paragraph("A4. LOW SEVERITY ISSUES", S_H2))
    story.append(sp(4))

    low_issues = [
        ("L1", "Zero Test Coverage for Critical Modules",
         "exit_intelligence.py (trade exits), agent_e.py (sector guard), "
         "api_server.py (1000+ LOC), database_security.py, coordinator.py (21KB) "
         "all have ZERO tests."),
        ("L2", "Dead Code and Unused Variables",
         "agent_a.py:74 _global_ohlcv_buffer never used. swarm_predictor.py:169 "
         "self._api_url never referenced. dms.py:104 unreachable return. "
         "system_config.py:41-63 most config flags never read by any code."),
        ("L3", "Frontend Integration Gaps",
         "vite.config.js proxy has no timeout/health check. main.jsx has no error "
         "boundary. cockpit.py:149 shows hardcoded fake positions."),
        ("L4", "Logging Configuration Issues",
         "Multiple files create loggers without configuring root logger. "
         "data_pipeline.py calls basicConfig() in module init. Log files use "
         "UTF-16LE but Python expects UTF-8."),
        ("L5", "Inconsistent Return Types Across Pattern Detectors",
         "agent_a.py pattern detectors return PatternResult|None but callers "
         "don't always check for None before accessing attributes."),
        ("L6", "Memory Unbounded in Mind Bridge",
         "mind_bridge.py:72-73 allows 1000 messages in dialogue_history using "
         "list.pop(0) which is O(n). Should use collections.deque."),
        ("L7", "Freshness Score Not Cached",
         "agent_b.py:156 recalculates freshness on every classify() call. "
         "Should cache with a short TTL."),
        ("L8", "Type Confusion in Vault",
         "vault.py:62 str(default) conversion if default is not string could "
         "produce unexpected results."),
        ("L9", "ChromaDB Fallback to Ephemeral Not Logged as Critical",
         "swarm_predictor.py:92 falls back to ephemeral ChromaDB client. "
         "All vector memory is lost but only logged at WARNING level."),
        ("L10", "Missing .gitignore for Sensitive Files",
         "No evidence of .gitignore protecting .env files, trading.db, "
         "log files, or vault credentials from accidental commits."),
    ]

    for lid, title, detail in low_issues:
        story.append(KeepTogether([
            Paragraph(f'<font color="{CLR_TEXT_LIGHT.hexval()}">[{lid}]</font> '
                      f'<b>{title}</b>', S_H3),
            Paragraph(detail, S_BODY),
            sp(3),
        ]))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PART B: STEP-BY-STEP REMEDIATION PLAN
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("PART B: STEP-BY-STEP REMEDIATION PLAN", S_H1))
    story.append(Paragraph(
        "30 concrete steps organized into 9 phases. Each step tells you exactly "
        "which file to open, what to change, and how to verify the fix. "
        "Follow phases in order - later phases depend on earlier ones.",
        S_BODY))
    story.append(hr())

    # ── PHASE 1 ─────────────────────────────────────────────────
    story.extend(phase_header(1, "STOP THE BLEEDING - Critical Fixes",
        "These fixes prevent runtime crashes and financial risk. Do these first."))

    # Step 1
    story.append(step_header(1, "Fix Python Version Mismatch"))
    story.append(Paragraph("Resolves: C1 | Files: .python-version, pyproject.toml, "
                           "requirements.txt, system_config.py", S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph("<b>Option A - Downgrade to 3.11.9 (Recommended):</b>", S_BODY))
    story.append(bullet("Install Python 3.11.9 via pyenv or direct download"))
    story.append(code_block("pyenv install 3.11.9\npyenv local 3.11.9"))
    story.append(bullet("Delete existing venv and recreate:"))
    story.append(code_block("rm -rf venv\npython -m venv venv\nvenv\\Scripts\\activate\npip install -r requirements.txt"))
    story.append(bullet("Run tests to verify all dependencies work:"))
    story.append(code_block("pytest tests/ -x --tb=short"))
    story.append(sp(3))
    story.append(Paragraph("<b>Option B - Keep 3.14.3 (More work):</b>", S_BODY))
    story.append(bullet("Update .python-version to: 3.14.3"))
    story.append(bullet("Update pyproject.toml: target-version = \"py314\""))
    story.append(bullet("Update requirements.txt header comment"))
    story.append(bullet("Update system_config.py: PYTHON_TARGET = \"3.14.3\""))
    story.append(bullet("Test every dependency for 3.14 compatibility"))
    story.append(sp(3))
    story.append(Paragraph("<b>Verification:</b>", S_BODY))
    story.append(code_block("python --version  # Should match config\npytest tests/ -x  # All tests should run (even if some fail)"))
    story.append(tip_box("Option A is safer. Python 3.14 is very new and many trading "
                         "libraries may not support it yet."))
    story.append(sp(8))

    # Step 2
    story.append(step_header(2, "Fix DMS Infinite Recursion"))
    story.append(Paragraph("Resolves: C2 | File: src/dms.py : lines 211-214", S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph("<b>Current code (broken):</b>", S_BODY))
    story.append(code_block(
        "async def execute_emergency_flatten(self):\n"
        "    # ... reconnect logic ...\n"
        "    return await self.execute_emergency_flatten()  # INFINITE RECURSION"))
    story.append(Paragraph("<b>Fix - Replace recursive call with retry loop:</b>", S_BODY))
    story.append(code_block(
        "async def execute_emergency_flatten(self, _retries: int = 3):\n"
        "    for attempt in range(1, _retries + 1):\n"
        "        try:\n"
        "            # ... existing flatten logic ...\n"
        "            return True\n"
        "        except ConnectionError:\n"
        "            logger.warning(f\"Flatten attempt {attempt}/{_retries} failed\")\n"
        "            await self._reconnect_ibkr()\n"
        "            await asyncio.sleep(2 ** attempt)  # exponential backoff\n"
        "    # All retries exhausted\n"
        "    logger.critical(\"EMERGENCY FLATTEN FAILED AFTER ALL RETRIES\")\n"
        "    await self._send_emergency_alert(\"Flatten failed - manual intervention needed\")\n"
        "    return False"))
    story.append(Paragraph("<b>Verification:</b>", S_BODY))
    story.append(bullet("Write a unit test that mocks IBKR connection to fail 5 times"))
    story.append(bullet("Verify it stops after 3 retries (not infinite)"))
    story.append(bullet("Verify emergency alert is sent on final failure"))
    story.append(sp(8))

    # Step 3
    story.append(step_header(3, "Fix SQL Injection Vulnerabilities"))
    story.append(Paragraph("Resolves: C3 | Files: src/agent_c.py:121-123, "
                           "src/questdb_adapter.py:322", S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph("<b>Fix #1 - agent_c.py (ATTACH DATABASE):</b>", S_BODY))
    story.append(code_block(
        "# BEFORE (vulnerable):\n"
        "cursor.execute(f\"ATTACH DATABASE '{main_db_path}' AS main_db\")\n\n"
        "# AFTER (safe):\n"
        "from pathlib import Path\n"
        "safe_path = str(Path(main_db_path).resolve())\n"
        "assert safe_path.endswith('.db'), \"Invalid database path\"\n"
        "# ATTACH doesn't support parameters, so validate the path strictly\n"
        "if not Path(safe_path).exists():\n"
        "    raise FileNotFoundError(f\"DB not found: {safe_path}\")\n"
        "cursor.execute(f\"ATTACH DATABASE '{safe_path}' AS main_db\")"))
    story.append(sp(3))
    story.append(Paragraph("<b>Fix #2 - questdb_adapter.py (DROP PARTITION):</b>", S_BODY))
    story.append(code_block(
        "# BEFORE (vulnerable):\n"
        "cursor.execute(f\"ALTER TABLE ohlcv DROP PARTITION '{stale_date}';\")\n\n"
        "# AFTER (safe):\n"
        "import re\n"
        "if not re.match(r'^\\d{4}-\\d{2}-\\d{2}$', stale_date):\n"
        "    raise ValueError(f\"Invalid date format: {stale_date}\")\n"
        "cursor.execute(f\"ALTER TABLE ohlcv DROP PARTITION '{stale_date}';\")"))
    story.append(sp(8))

    # Step 4
    story.append(step_header(4, "Fix Division-by-Zero Crashes"))
    story.append(Paragraph("Resolves: C5 | Files: 4 locations", S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph("<b>Fix each location:</b>", S_BODY))
    story.append(sp(2))
    story.append(Paragraph("<b>1. src/exit_intelligence.py : line 56</b>", S_BODY))
    story.append(code_block(
        "# Add before slippage calculation:\n"
        "if qty == 0:\n"
        "    return 0.0"))
    story.append(Paragraph("<b>2. src/agent_c.py : line 142</b>", S_BODY))
    story.append(code_block(
        "# Replace: win_rate = wins / total\n"
        "win_rate = wins / total if total > 0 else 0.0"))
    story.append(Paragraph("<b>3. src/mind_ultrathink.py : line 85</b>", S_BODY))
    story.append(code_block(
        "# Replace: avg = sum(...) / len(resonance_results)\n"
        "avg = sum(...) / len(resonance_results) if resonance_results else 0.0"))
    story.append(Paragraph("<b>4. src/coordinator.py : line 246</b>", S_BODY))
    story.append(code_block(
        "# Replace:\n"
        "# entry_price = getattr(p, 'entry_price', 0) or 0\n"
        "# With:\n"
        "entry_price = getattr(p, 'entry_price', None)\n"
        "if entry_price is None:\n"
        "    logger.warning(f\"Position {p} has no entry_price, skipping\")\n"
        "    continue"))
    story.append(sp(8))

    # Step 5
    story.append(step_header(5, "Fix Polars API Call"))
    story.append(Paragraph("Resolves: C6 | File: src/agent_a.py : line 278", S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE (crashes - method doesn't exist):\n"
        "neckline = df[\"low\"][-30:].rolling_min()\n\n"
        "# AFTER (correct Polars API):\n"
        "neckline = df[\"low\"].tail(30).min()  # if you want a single min value\n"
        "# OR for a rolling minimum:\n"
        "neckline = df[\"low\"].tail(30).rolling_min(window_size=5)"))
    story.append(Paragraph("<b>Verification:</b>", S_BODY))
    story.append(code_block(
        "import polars as pl\n"
        "test_df = pl.DataFrame({\"low\": list(range(100))})\n"
        "result = test_df[\"low\"].tail(30).min()  # Should work without error"))
    story.append(sp(8))

    # Step 6
    story.append(step_header(6, "Fix Critical Bare Exception Handlers"))
    story.append(Paragraph("Resolves: C4 | Files: 6 locations", S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph(
        "For each location, replace the bare except with specific exception types, "
        "proper logging, and appropriate escalation:", S_BODY))
    story.append(sp(3))

    story.append(Paragraph("<b>1. src/agent_c.py : line 112 (Trade execution)</b>", S_BODY))
    story.append(code_block(
        "# BEFORE:\n"
        "except Exception as e:\n"
        "    logger.error(f\"DB error: {e}\")\n"
        "    pass\n\n"
        "# AFTER:\n"
        "except sqlite3.IntegrityError as e:\n"
        "    logger.warning(f\"Duplicate trade record: {e}\")\n"
        "except sqlite3.OperationalError as e:\n"
        "    logger.critical(f\"Database failure during trade: {e}\")\n"
        "    raise  # Must propagate - trade state is unknown"))

    story.append(Paragraph("<b>2. src/data_pipeline.py : lines 258, 321 (Data fetch)</b>",
                           S_BODY))
    story.append(code_block(
        "# BEFORE:\n"
        "except Exception as e:\n"
        "    logger.error(f\"Fetch failed: {e}\")\n"
        "    return None\n\n"
        "# AFTER:\n"
        "except httpx.TimeoutException as e:\n"
        "    logger.warning(f\"Data fetch timeout for {symbol}: {e}\")\n"
        "    return None  # Caller knows to retry\n"
        "except httpx.HTTPStatusError as e:\n"
        "    logger.error(f\"API error {e.response.status_code} for {symbol}\")\n"
        "    raise DataFetchError(symbol, e) from e"))

    story.append(Paragraph("<b>3. src/dms.py : line 101 (Telegram alert)</b>", S_BODY))
    story.append(code_block(
        "# BEFORE:\n"
        "except Exception as e:\n"
        "    logger.error(f\"Telegram failed: {e}\")\n\n"
        "# AFTER:\n"
        "except Exception as e:\n"
        "    logger.critical(f\"TELEGRAM ALERT FAILED: {e}\")\n"
        "    # Fallback: write to emergency file\n"
        "    Path(\"EMERGENCY_ALERT.txt\").write_text(\n"
        "        f\"{datetime.now()}: {message}\\nTelegram error: {e}\")\n"
        "    raise  # DMS alerts are life-critical"))

    story.append(Paragraph("<b>Apply similar pattern to remaining 3 locations</b> "
                           "(swarm_predictor.py:309+394, questdb_adapter.py:124): "
                           "catch specific exceptions, log at appropriate severity, "
                           "re-raise or return sentinel values that callers check.", S_BODY))
    story.append(PageBreak())

    # ── PHASE 2 ─────────────────────────────────────────────────
    story.extend(phase_header(2, "SECURITY HARDENING",
        "Close security vulnerabilities and protect credentials."))

    # Step 7
    story.append(step_header(7, "Remove Hardcoded Secrets"))
    story.append(Paragraph("Resolves: H1 | Files: session_restorer.py, questdb_adapter.py, "
                           "mind_system.py, system_config.py", S_BODY_SMALL))
    story.append(sp(3))
    story.append(bullet("<b>session_restorer.py:27</b> - Move secret to Vault:"))
    story.append(code_block(
        "# BEFORE: self.secret_key = \"SETO_ABSOLUTE_V6\"\n"
        "# AFTER:\n"
        "self.secret_key = Vault.get(\"SESSION_SECRET_KEY\")\n"
        "if not self.secret_key:\n"
        "    raise RuntimeError(\"SESSION_SECRET_KEY not configured in Vault\")"))
    story.append(bullet("<b>questdb_adapter.py:30</b> - Require explicit password:"))
    story.append(code_block(
        "# BEFORE: password: str = \"quest\"\n"
        "# AFTER:\n"
        "password: str = Vault.get(\"QUESTDB_PASSWORD\")\n"
        "if not password:\n"
        "    raise RuntimeError(\"QUESTDB_PASSWORD not configured\")"))
    story.append(bullet("<b>system_config.py:49-51</b> - Remove all API key references. "
                        "Keys should only be accessed via Vault at point of use."))
    story.append(bullet("<b>mind_system.py:96</b> - Make IBKR path configurable:"))
    story.append(code_block("ibkr_path = Vault.get(\"IBKR_INSTALL_PATH\", \"C:\\\\Jts\")"))
    story.append(sp(8))

    # Step 8
    story.append(step_header(8, "Fix API Key Exposure in URLs"))
    story.append(Paragraph("Resolves: H2 | File: src/data_pipeline.py : line 276",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE:\n"
        "url = f\"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}\"\n"
        "resp = await client.get(url)\n\n"
        "# AFTER:\n"
        "url = f\"https://finnhub.io/api/v1/quote?symbol={symbol}\"\n"
        "resp = await client.get(url, headers={\"X-Finnhub-Token\": self.finnhub_key})"))
    story.append(bullet("Also add a log filter to redact API keys:"))
    story.append(code_block(
        "class SecretFilter(logging.Filter):\n"
        "    def __init__(self, secrets: list[str]):\n"
        "        self.secrets = secrets\n"
        "    def filter(self, record):\n"
        "        msg = record.getMessage()\n"
        "        for s in self.secrets:\n"
        "            if s and s in msg:\n"
        "                record.msg = record.msg.replace(s, \"***REDACTED***\")\n"
        "        return True"))
    story.append(sp(8))

    # Step 9
    story.append(step_header(9, "Fix Command Injection Risks"))
    story.append(Paragraph("Resolves: H5 | File: src/mind_system.py : lines 127, 215",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE (line 127):\n"
        "cmd = f'start \"\" \"{path}\"'\n"
        "os.system(cmd)\n\n"
        "# AFTER:\n"
        "import subprocess\n"
        "subprocess.Popen([path], shell=False)\n\n"
        "# BEFORE (line 215):\n"
        "cmd = f'taskkill /F /FI \"IMAGENAME eq {target}\"'\n"
        "os.system(cmd)\n\n"
        "# AFTER:\n"
        "subprocess.run(\n"
        "    [\"taskkill\", \"/F\", \"/FI\", f\"IMAGENAME eq {target}\",\n"
        "     \"/FI\", f\"PID ne {my_pid}\", \"/T\"],\n"
        "    check=False\n"
        ")"))
    story.append(sp(8))

    # Step 10
    story.append(step_header(10, "Fix Pickle Vulnerability"))
    story.append(Paragraph("Resolves: H4 | File: src/session_restorer.py : line 127",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE:\n"
        "bundle = pickle.loads(data)\n\n"
        "# AFTER:\n"
        "try:\n"
        "    bundle = pickle.loads(data)\n"
        "except (pickle.UnpicklingError, AttributeError, EOFError, TypeError) as e:\n"
        "    logger.error(f\"Corrupted session file: {e}\")\n"
        "    return None\n\n"
        "# Validate structure\n"
        "required_keys = {\"brain_state\", \"positions\", \"timestamp\"}\n"
        "if not isinstance(bundle, dict) or not required_keys.issubset(bundle.keys()):\n"
        "    logger.error(f\"Invalid session structure: {bundle.keys() if isinstance(bundle, dict) else type(bundle)}\")\n"
        "    return None"))
    story.append(sp(3))
    story.append(tip_box(
        "<b>Long-term:</b> Migrate from pickle to JSON for session state. "
        "JSON is human-readable, can't execute code, and is easier to debug."))
    story.append(sp(8))

    # Step 11
    story.append(step_header(11, "Replace Caller Verification with Proper Access Control"))
    story.append(Paragraph("Resolves: H6 | File: src/agent_c_ibkr.py : lines 130, 176, 251",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE (weak, bypassable):\n"
        "caller = inspect.currentframe().f_back.f_code.co_qualname\n"
        "if 'Coordinator' not in caller:\n"
        "    raise PermissionError(\"Unauthorized\")\n\n"
        "# AFTER (proper token-based access):\n"
        "import secrets\n\n"
        "class AgentC_IBKR:\n"
        "    _auth_token: str = secrets.token_hex(32)\n\n"
        "    def execute_trade(self, *, auth_token: str, **kwargs):\n"
        "        if auth_token != self._auth_token:\n"
        "            raise PermissionError(\"Invalid authorization token\")\n"
        "        # ... trade logic ...\n\n"
        "# Coordinator receives token at initialization:\n"
        "# self.agent_c_token = agent_c.get_auth_token()"))
    story.append(PageBreak())

    # ── PHASE 3 ─────────────────────────────────────────────────
    story.extend(phase_header(3, "RACE CONDITIONS & ASYNC FIXES",
        "Fix concurrent access issues that cause state corruption."))

    # Step 12
    story.append(step_header(12, "Add Locks to All Shared Mutable State"))
    story.append(Paragraph("Resolves: H3 | Files: coordinator.py, dms.py, "
                           "intelligence_bus.py, api_cache.py", S_BODY_SMALL))
    story.append(sp(3))

    story.append(Paragraph("<b>1. coordinator.py : _pending_vets</b>", S_BODY))
    story.append(code_block(
        "# In __init__:\n"
        "self._pending_vets: set = set()\n"
        "self._vet_lock = asyncio.Lock()  # ADD THIS\n\n"
        "# Every access to _pending_vets:\n"
        "async with self._vet_lock:\n"
        "    self._pending_vets.add(symbol)\n"
        "# ... and ...\n"
        "async with self._vet_lock:\n"
        "    self._pending_vets.discard(symbol)"))

    story.append(Paragraph("<b>2. dms.py : alert_sent, flatten_executed</b>", S_BODY))
    story.append(code_block(
        "# In __init__:\n"
        "self._state_lock = asyncio.Lock()\n\n"
        "# Every read/write of flags:\n"
        "async with self._state_lock:\n"
        "    if not self.alert_sent:\n"
        "        self.alert_sent = True\n"
        "        await self._send_alert(...)"))

    story.append(Paragraph("<b>3. intelligence_bus.py : _subscribers, _callbacks</b>", S_BODY))
    story.append(code_block(
        "# In __init__:\n"
        "self._sub_lock = asyncio.Lock()\n\n"
        "async def subscribe(self, topic, callback):\n"
        "    async with self._sub_lock:\n"
        "        self._subscribers.setdefault(topic, []).append(callback)\n\n"
        "async def publish(self, topic, data):\n"
        "    async with self._sub_lock:\n"
        "        callbacks = list(self._subscribers.get(topic, []))\n"
        "    # Execute callbacks OUTSIDE the lock to avoid deadlocks\n"
        "    for cb in callbacks:\n"
        "        await cb(data)"))

    story.append(Paragraph("<b>4. api_cache.py : _store</b>", S_BODY))
    story.append(code_block(
        "# Move min() call INSIDE the existing lock:\n"
        "with self._lock:\n"
        "    if len(self._store) >= self._max_size:\n"
        "        oldest = min(self._store, key=lambda k: self._store[k][1])\n"
        "        del self._store[oldest]"))
    story.append(sp(8))

    # Step 13
    story.append(step_header(13, "Fix asyncio Queue Initialization"))
    story.append(Paragraph("Resolves: M11 | File: src/questdb_adapter.py : line 42",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE:\n"
        "def __init__(self, ...):\n"
        "    self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)\n\n"
        "# AFTER - lazy initialization:\n"
        "def __init__(self, ...):\n"
        "    self._queue = None\n\n"
        "def _get_queue(self):\n"
        "    if self._queue is None:\n"
        "        self._queue = asyncio.Queue(maxsize=10000)\n"
        "    return self._queue"))
    story.append(sp(8))

    # Step 14
    story.append(step_header(14, "Fix IBKR Connection Strategy"))
    story.append(Paragraph("Resolves: M12 | File: src/ibkr_streamer.py : lines 65-84",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE: 150 combinations x 0.5s = 75 seconds\n\n"
        "# AFTER: configurable targets with exponential backoff\n"
        "IBKR_TARGETS = [\n"
        "    (\"127.0.0.1\", 7497, 1),   # TWS paper\n"
        "    (\"127.0.0.1\", 7496, 1),   # TWS live\n"
        "    (\"127.0.0.1\", 4002, 1),   # Gateway paper\n"
        "    (\"127.0.0.1\", 4001, 1),   # Gateway live\n"
        "]\n\n"
        "async def connect(self, max_retries: int = 3):\n"
        "    for attempt in range(max_retries):\n"
        "        for host, port, client_id in IBKR_TARGETS:\n"
        "            try:\n"
        "                ib = IB()\n"
        "                await ib.connectAsync(host, port, clientId=client_id, timeout=5)\n"
        "                logger.info(f\"Connected to IBKR at {host}:{port}\")\n"
        "                return ib\n"
        "            except ConnectionRefusedError:\n"
        "                continue\n"
        "        wait = 2 ** attempt\n"
        "        logger.warning(f\"IBKR attempt {attempt+1} failed, retry in {wait}s\")\n"
        "        await asyncio.sleep(wait)\n"
        "    raise ConnectionError(\"Failed to connect to IBKR after all retries\")"))
    story.append(PageBreak())

    # ── PHASE 4 ─────────────────────────────────────────────────
    story.extend(phase_header(4, "LOGIC BUG FIXES",
        "Fix incorrect trading logic that leads to wrong decisions."))

    # Step 15
    story.append(step_header(15, "Fix Pattern Detection Logic"))
    story.append(Paragraph("Resolves: M1, M2 | Files: agent_b.py, agent_a.py",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph("<b>1. Fix falling wedge convergence (agent_b.py:328-333):</b>",
                           S_BODY))
    story.append(code_block(
        "# BEFORE (inverted logic):\n"
        "if high_coef[0] >= low_coef[0]:  # \"not converging\"\n\n"
        "# AFTER:\n"
        "# For falling wedge: both slopes negative, high slope less negative than low\n"
        "# i.e., lines converge downward\n"
        "if high_coef[0] < low_coef[0]:  # Lines converging = valid wedge\n"
        "    # ... pattern confirmed ..."))
    story.append(sp(3))
    story.append(Paragraph("<b>2. Use config for confidence threshold (agent_a.py:922):</b>",
                           S_BODY))
    story.append(code_block(
        "# BEFORE:\n"
        "if pattern.confidence < 60.0:\n\n"
        "# AFTER:\n"
        "from config import BELIEF_CAP_MIN  # or appropriate config key\n"
        "if pattern.confidence < BELIEF_CAP_MIN:"))
    story.append(sp(8))

    # Step 16
    story.append(step_header(16, "Fix Coordinator Cash Reserve Check"))
    story.append(Paragraph("Resolves: M4 | File: src/coordinator.py : lines 236-238",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE:\n"
        "if confidence > 68:\n"
        "    shares = 5  # No cash check!\n\n"
        "# AFTER:\n"
        "if confidence > 68:\n"
        "    proposed_shares = 5\n"
        "    cost = proposed_shares * price\n"
        "    available = self.get_available_cash()\n"
        "    reserve = available * config.CASH_RESERVE_RATIO\n"
        "    if cost > (available - reserve):\n"
        "        shares = max(1, int((available - reserve) / price))\n"
        "        logger.warning(f\"Reduced shares from {proposed_shares} to {shares} (cash reserve)\")\n"
        "    else:\n"
        "        shares = proposed_shares"))
    story.append(sp(8))

    # Step 17
    story.append(step_header(17, "Fix Ghost Timer"))
    story.append(Paragraph("Resolves: M3 | File: src/mind_ghost.py : lines 63-64",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE (unreliable modulo):\n"
        "if int(current_time) % 15 == 0:\n\n"
        "# AFTER (proper interval tracking):\n"
        "# In __init__:\n"
        "self._last_check = time.monotonic()\n\n"
        "# In the loop:\n"
        "now = time.monotonic()\n"
        "if now - self._last_check >= 15:\n"
        "    self._last_check = now\n"
        "    # ... do the periodic work ..."))
    story.append(sp(8))

    # Step 18
    story.append(step_header(18, "Fix DMS Contract Qualification"))
    story.append(Paragraph("Resolves: M5 | File: src/dms.py : line 184", S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE:\n"
        "await self.ibkr_client.qualifyContractsAsync(pos.contract)\n\n"
        "# AFTER:\n"
        "qualified = await self.ibkr_client.qualifyContractsAsync(pos.contract)\n"
        "if not qualified:\n"
        "    logger.error(f\"Failed to qualify contract: {pos.contract}\")\n"
        "    continue  # Skip this position"))
    story.append(PageBreak())

    # ── PHASE 5 ─────────────────────────────────────────────────
    story.extend(phase_header(5, "STUB IMPLEMENTATIONS",
        "Address fake/placeholder code that pretends to provide intelligence."))

    # Step 19
    story.append(step_header(19, "Audit and Resolve All Stubs"))
    story.append(Paragraph("Resolves: M6 | Files: 5 modules", S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph(
        "For each stub, you must decide: <b>implement it</b> or <b>remove it</b>. "
        "Do NOT leave fake data flowing into real trading decisions.", S_BODY))
    story.append(sp(3))

    stub_table = make_table(
        ["Stub", "File", "Current Behavior", "Action"],
        [
            ["_tool_fetch_sentiment()", "mind_observer.py:78",
             "Always returns BULLISH", "Implement real API or remove"],
            ["_tool_scan_environment()", "mind_observer.py:87",
             "Always returns CLEAN", "Implement real scan or remove"],
            ["_tool_optimize_thresholds()", "mind_evolution.py:85",
             "Returns static dict", "Implement or remove"],
            ["_tool_evolve_strategy()", "mind_evolution.py:91",
             "Always returns success", "Implement or remove"],
            ["_process_strategic_dialogue()", "mind_evolution.py:77",
             "Empty pass", "Implement or remove"],
            ["_monitor_shadow_tests()", "mind_experiment.py:36",
             "Sleeps 600s forever", "Implement or remove"],
            ["Evolution cycle", "agent_c.py:170",
             "pass after logging", "Implement or remove"],
        ],
        col_widths=[1.7*inch, 1.4*inch, 1.3*inch, 1.3*inch]
    )
    story.append(stub_table)
    story.append(sp(6))
    story.append(danger_box(
        "The mind_observer always returning BULLISH/CLEAN is especially dangerous. "
        "If any trading logic depends on sentiment or environment scans, it will "
        "ALWAYS receive positive signals regardless of actual market conditions."))
    story.append(sp(3))
    story.append(Paragraph("<b>If keeping a stub temporarily:</b>", S_BODY))
    story.append(code_block(
        "async def _tool_fetch_sentiment(self, symbol: str) -> str:\n"
        "    logger.warning(f\"STUB: sentiment for {symbol} returning NEUTRAL (not real)\")\n"
        "    return \"NEUTRAL\"  # Safe default, not BULLISH"))
    story.append(PageBreak())

    # ── PHASE 6 ─────────────────────────────────────────────────
    story.extend(phase_header(6, "PERFORMANCE OPTIMIZATION",
        "Fix bottlenecks that waste resources and slow the system."))

    # Step 20
    story.append(step_header(20, "Fix WebSocket State Push"))
    story.append(Paragraph("Resolves: M7 | File: src/api_server.py : lines 188, 261-282",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(bullet("Cache OHLCV data with a 5-second TTL:"))
    story.append(code_block(
        "_ohlcv_cache = {}  # {symbol: (data, timestamp)}\n"
        "OHLCV_CACHE_TTL = 5.0\n\n"
        "async def get_ohlcv_cached(symbol: str):\n"
        "    now = time.time()\n"
        "    if symbol in _ohlcv_cache:\n"
        "        data, ts = _ohlcv_cache[symbol]\n"
        "        if now - ts < OHLCV_CACHE_TTL:\n"
        "            return data\n"
        "    data = await fetch_ohlcv(symbol)\n"
        "    _ohlcv_cache[symbol] = (data, now)\n"
        "    return data"))
    story.append(bullet("Increase WebSocket push interval from 1s to 2-3s"))
    story.append(bullet("Implement delta updates: only send changed fields"))
    story.append(sp(8))

    # Step 21
    story.append(step_header(21, "Fix OHLCV Buffer Copying"))
    story.append(Paragraph("Resolves: M8 | File: src/agent_a.py : lines 46-68",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# Instead of copying the entire array every scan,\n"
        "# only append new bars:\n\n"
        "def update_from_df(self, df: pl.DataFrame):\n"
        "    if self._last_timestamp is not None:\n"
        "        new_bars = df.filter(pl.col(\"timestamp\") > self._last_timestamp)\n"
        "    else:\n"
        "        new_bars = df\n"
        "    if len(new_bars) > 0:\n"
        "        self._data = pl.concat([self._data, new_bars]).tail(self._max_size)\n"
        "        self._last_timestamp = new_bars[\"timestamp\"][-1]"))
    story.append(sp(8))

    # Step 22
    story.append(step_header(22, "Increase Concurrency Limit"))
    story.append(Paragraph("Resolves: M9 | File: src/coordinator.py : line 48",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE:\n"
        "CONCURRENCY_LIMIT = 3\n\n"
        "# AFTER - make it configurable:\n"
        "CONCURRENCY_LIMIT = int(config.get(\"CONCURRENCY_LIMIT\", 8))"))
    story.append(PageBreak())

    # ── PHASE 7 ─────────────────────────────────────────────────
    story.extend(phase_header(7, "CONFIGURATION CLEANUP",
        "Eliminate config drift and fix logging."))

    # Step 23
    story.append(step_header(23, "Unify Configuration Files"))
    story.append(Paragraph("Resolves: M10 | Files: src/config.py, system_config.py",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(Paragraph("<b>Action plan:</b>", S_BODY))
    story.append(bullet("Choose ONE config file as the source of truth (recommend src/config.py)"))
    story.append(bullet("Move all settings from system_config.py into src/config.py"))
    story.append(bullet("Delete system_config.py"))
    story.append(bullet("Update all imports across the codebase"))
    story.append(bullet("Define clear precedence:"))
    story.append(code_block(
        "# Priority order (highest to lowest):\n"
        "# 1. Vault (for secrets)\n"
        "# 2. Environment variables (for deployment overrides)\n"
        "# 3. Config file defaults (for development)\n\n"
        "def get_config(key: str, default=None):\n"
        "    # Secrets always from Vault\n"
        "    if key in SECRET_KEYS:\n"
        "        return Vault.get(key) or default\n"
        "    # Everything else: env > config > default\n"
        "    return os.environ.get(key) or CONFIG_DEFAULTS.get(key) or default"))
    story.append(bullet("Add startup validation:"))
    story.append(code_block(
        "REQUIRED_KEYS = [\"IBKR_ACCOUNT_ID\", \"TOTAL_CAPITAL\", \"QUESTDB_PASSWORD\"]\n\n"
        "def validate_config():\n"
        "    missing = [k for k in REQUIRED_KEYS if not get_config(k)]\n"
        "    if missing:\n"
        "        raise RuntimeError(f\"Missing required config: {', '.join(missing)}\")"))
    story.append(sp(8))

    # Step 24
    story.append(step_header(24, "Fix Logging Configuration"))
    story.append(Paragraph("Resolves: L4 | Files: src/main.py, src/data_pipeline.py",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(bullet("Configure root logger ONCE in src/main.py:"))
    story.append(code_block(
        "import logging\n\n"
        "def setup_logging():\n"
        "    root = logging.getLogger()\n"
        "    root.setLevel(logging.INFO)\n\n"
        "    # File handler with explicit UTF-8\n"
        "    fh = logging.FileHandler(\"logs/trading.log\", encoding=\"utf-8\")\n"
        "    fh.setFormatter(logging.Formatter(\n"
        "        \"%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s\"))\n"
        "    root.addHandler(fh)\n\n"
        "    # Console handler\n"
        "    ch = logging.StreamHandler()\n"
        "    ch.setFormatter(logging.Formatter(\"%(levelname)-7s | %(message)s\"))\n"
        "    root.addHandler(ch)"))
    story.append(bullet("Remove logging.basicConfig() from data_pipeline.py:22"))
    story.append(bullet("Remove any other basicConfig() calls across the codebase"))
    story.append(PageBreak())

    # ── PHASE 8 ─────────────────────────────────────────────────
    story.extend(phase_header(8, "TEST COVERAGE",
        "Fix broken tests and add coverage for critical untested modules."))

    # Step 25
    story.append(step_header(25, "Fix Broken Test Fixtures"))
    story.append(Paragraph("Resolves: C7 | File: tests/test_trading_brain.py",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "# BEFORE (broken):\n"
        "@pytest.fixture\n"
        "def brain():\n"
        "    with patch('sqlite3.connect'):  # Double mocking!\n"
        "        mock_db = MagicMock()\n"
        "        b = TradingBrain(db_path='test.db')  # Wrong kwarg!\n"
        "        return b\n\n"
        "# AFTER (correct):\n"
        "@pytest.fixture\n"
        "def brain():\n"
        "    mock_db = MagicMock(spec=sqlite3.Connection)\n"
        "    mock_db.cursor.return_value = MagicMock()\n"
        "    b = TradingBrain(db_conn=mock_db)  # Match actual signature\n"
        "    # Configure AsyncMock for regime detection:\n"
        "    b._detect_regime = AsyncMock(return_value=\"BULL\")\n"
        "    return b"))
    story.append(sp(8))

    # Step 26
    story.append(step_header(26, "Write Missing Tests (Priority Order)"))
    story.append(Paragraph("Resolves: L1 | Files: new test files", S_BODY_SMALL))
    story.append(sp(3))

    test_table = make_table(
        ["Priority", "Module", "Test File", "Key Test Cases"],
        [
            ["1 (Critical)", "exit_intelligence.py",
             "tests/test_exit_intelligence.py",
             "Slippage with qty=0, runner logic, missing keys"],
            ["2 (Critical)", "coordinator.py",
             "tests/test_coordinator.py",
             "Concurrent vetting, cash reserve, semaphore"],
            ["3 (High)", "agent_e.py",
             "tests/test_agent_e.py",
             "Sector guard logic, edge cases"],
            ["4 (High)", "api_server.py",
             "tests/test_api_server.py",
             "All endpoints, WebSocket, error handling"],
            ["5 (Medium)", "database_security.py",
             "tests/test_db_security.py",
             "Encryption round-trip, key rotation"],
        ],
        col_widths=[0.9*inch, 1.3*inch, 1.7*inch, 1.9*inch]
    )
    story.append(test_table)
    story.append(sp(8))

    # Step 27
    story.append(step_header(27, "Improve Test Fixtures"))
    story.append(Paragraph("Resolves: L1 | File: tests/conftest.py", S_BODY_SMALL))
    story.append(sp(3))
    story.append(bullet("Add <b>mock_vault</b> fixture (prevents tests from reading real creds):"))
    story.append(code_block(
        "@pytest.fixture(autouse=True)\n"
        "def mock_vault(monkeypatch):\n"
        "    test_secrets = {\n"
        "        \"IBKR_ACCOUNT_ID\": \"TEST123\",\n"
        "        \"TOTAL_CAPITAL\": \"100000\",\n"
        "        \"QUESTDB_PASSWORD\": \"testpass\",\n"
        "    }\n"
        "    monkeypatch.setattr(\"vault.Vault.get\",\n"
        "        lambda key, default=None: test_secrets.get(key, default))"))
    story.append(bullet("Upgrade <b>sample_ohlcv_df</b> to support realistic patterns:"))
    story.append(code_block(
        "@pytest.fixture\n"
        "def ohlcv_factory():\n"
        "    def make(bars=100, trend=\"flat\", volatility=0.02):\n"
        "        # Generate realistic OHLCV with configurable patterns\n"
        "        ...\n"
        "    return make"))
    story.append(PageBreak())

    # ── PHASE 9 ─────────────────────────────────────────────────
    story.extend(phase_header(9, "BUILD & DEPLOYMENT",
        "Fix deployment configuration and frontend integration."))

    # Step 28
    story.append(step_header(28, "Fix Docker Configuration"))
    story.append(Paragraph("Resolves: H7 | File: docker-compose.questdb.yml",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "services:\n"
        "  questdb:\n"
        "    image: questdb/questdb:latest\n"
        "    deploy:\n"
        "      resources:\n"
        "        limits:\n"
        "          memory: 4G\n"
        "          cpus: '2.0'\n"
        "    healthcheck:\n"
        "      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:9000/health\"]\n"
        "      interval: 10s\n"
        "      timeout: 5s\n"
        "      retries: 3\n"
        "    environment:\n"
        "      - QDB_CAIRO_MAX_UNFENCED_PARTITIONS=20\n"
        "      - QDB_IMPORT_TIMEOUT=300"))
    story.append(sp(8))

    # Step 29
    story.append(step_header(29, "Fix run_bot.bat"))
    story.append(Paragraph("Resolves: L3 | File: run_bot.bat", S_BODY_SMALL))
    story.append(sp(3))
    story.append(code_block(
        "REM Replace hardcoded Docker path:\n"
        "where docker >nul 2>nul\n"
        "if %ERRORLEVEL% neq 0 (\n"
        "    echo ERROR: Docker not found in PATH\n"
        "    exit /b 1\n"
        ")\n\n"
        "REM Add venv check:\n"
        "if not exist venv\\Scripts\\activate.bat (\n"
        "    echo ERROR: Virtual environment not found. Run setup first.\n"
        "    exit /b 1\n"
        ")"))
    story.append(sp(8))

    # Step 30
    story.append(step_header(30, "Fix Frontend Integration"))
    story.append(Paragraph("Resolves: L3 | Files: frontend/src/main.jsx, vite.config.js",
                           S_BODY_SMALL))
    story.append(sp(3))
    story.append(bullet("Add error boundary in main.jsx:"))
    story.append(code_block(
        "import { ErrorBoundary } from 'react-error-boundary'\n\n"
        "function ErrorFallback({ error }) {\n"
        "  return (\n"
        "    <div role=\"alert\">\n"
        "      <h2>Dashboard Error</h2>\n"
        "      <pre>{error.message}</pre>\n"
        "    </div>\n"
        "  )\n"
        "}\n\n"
        "root.render(\n"
        "  <ErrorBoundary FallbackComponent={ErrorFallback}>\n"
        "    <App />\n"
        "  </ErrorBoundary>\n"
        ")"))
    story.append(bullet("Add proxy timeout in vite.config.js:"))
    story.append(code_block(
        "proxy: {\n"
        "  '/api': {\n"
        "    target: 'http://localhost:8000',\n"
        "    changeOrigin: true,\n"
        "    timeout: 10000,  // 10 second timeout\n"
        "    rewrite: (path) => path.replace(/^\\/api/, '')\n"
        "  }\n"
        "}"))
    story.append(bullet("Remove hardcoded fake data from cockpit.py"))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PART C: ENHANCEMENT SUGGESTIONS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("PART C: ENHANCEMENT SUGGESTIONS", S_H1))
    story.append(Paragraph(
        "Beyond fixing bugs, these enhancements will make your system significantly "
        "more capable, robust, and profitable. Organized by category.", S_BODY))
    story.append(hr())

    # C1: Architecture
    story.append(Paragraph("C1. ARCHITECTURE ENHANCEMENTS", S_H2))
    story.append(sp(4))

    story.append(Paragraph("<b>E1. Event-Driven Architecture with Message Bus</b>", S_H3))
    story.append(Paragraph(
        "Replace direct function calls between agents with a proper event bus. "
        "Currently, agents call each other directly, creating tight coupling. "
        "An event-driven design allows agents to publish events (trade signals, "
        "risk alerts, data updates) and subscribe to events they care about. "
        "Benefits: agents can be added/removed without changing others, "
        "easier testing (mock the bus), better observability (log all events).",
        S_BODY))
    story.append(code_block(
        "# Example event flow:\n"
        "# Agent A detects pattern -> publishes PatternDetected event\n"
        "# Agent B receives event -> runs catalyst check -> publishes CatalystConfirmed\n"
        "# Coordinator receives both -> runs risk check -> publishes TradeProposal\n"
        "# Agent C receives proposal -> executes trade -> publishes TradeExecuted\n"
        "# DMS monitors TradeExecuted -> updates position tracking"))
    story.append(sp(6))

    story.append(Paragraph("<b>E2. State Machine for System Lifecycle</b>", S_H3))
    story.append(Paragraph(
        "Implement a formal state machine for the trading system's lifecycle: "
        "INITIALIZING -> CONNECTING -> SYNCING -> SCANNING -> TRADING -> SHUTTING_DOWN. "
        "Each state has defined entry/exit conditions and allowed transitions. "
        "This prevents trading during initialization, ensures clean shutdown, "
        "and makes the system's behavior predictable and debuggable.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E3. Circuit Breaker Pattern</b>", S_H3))
    story.append(Paragraph(
        "Add circuit breakers around all external service calls (IBKR, Finnhub, "
        "Ollama, QuestDB). When a service fails N times in M seconds, the circuit "
        "opens and subsequent calls fail fast instead of waiting for timeouts. "
        "After a cooldown period, the circuit half-opens to test if the service "
        "recovered. This prevents cascade failures where one slow service "
        "blocks the entire system.",
        S_BODY))
    story.append(code_block(
        "# Libraries: aiobreaker, pybreaker, or custom implementation\n"
        "from aiobreaker import CircuitBreaker\n\n"
        "ibkr_breaker = CircuitBreaker(\n"
        "    fail_max=3,\n"
        "    timeout_duration=timedelta(seconds=30)\n"
        ")\n\n"
        "@ibkr_breaker\n"
        "async def place_order(self, order):\n"
        "    return await self.ibkr.placeOrder(order)"))
    story.append(sp(6))

    story.append(Paragraph("<b>E4. Dependency Injection Container</b>", S_H3))
    story.append(Paragraph(
        "Replace hardcoded class instantiation with a DI container. Currently, "
        "agents create their own database connections, Vault instances, etc. "
        "A DI container provides these dependencies at construction time, "
        "making the code testable and configurable without modifying source.",
        S_BODY))
    story.append(PageBreak())

    # C2: AI/ML
    story.append(Paragraph("C2. AI/ML INTELLIGENCE UPGRADES", S_H2))
    story.append(sp(4))

    story.append(Paragraph("<b>E5. Implement Real Sentiment Analysis</b>", S_H3))
    story.append(Paragraph(
        "Replace the stub in mind_observer.py with actual sentiment analysis. "
        "Options: (a) Use a financial sentiment API like Alpha Vantage News Sentiment, "
        "(b) Run a local FinBERT model via Ollama for privacy, "
        "(c) Aggregate multiple sources (news headlines, social media, options flow). "
        "Weight by recency and source reliability.",
        S_BODY))
    story.append(code_block(
        "# Example with FinBERT via Ollama:\n"
        "async def fetch_sentiment(self, symbol: str) -> SentimentResult:\n"
        "    news = await self.fetch_recent_news(symbol, hours=4)\n"
        "    if not news:\n"
        "        return SentimentResult(signal=\"NEUTRAL\", confidence=0.0)\n"
        "    prompt = f\"Analyze sentiment for {symbol}: {news[:2000]}\"\n"
        "    result = await self.ollama.generate(model=\"finbert\", prompt=prompt)\n"
        "    return SentimentResult(\n"
        "        signal=result[\"sentiment\"],  # BULLISH/BEARISH/NEUTRAL\n"
        "        confidence=result[\"score\"],\n"
        "        sources=len(news)\n"
        "    )"))
    story.append(sp(6))

    story.append(Paragraph("<b>E6. Multi-Timeframe Confluence Engine</b>", S_H3))
    story.append(Paragraph(
        "Add a confluence scoring system that checks alignment across multiple "
        "timeframes (1m, 5m, 15m, 1h, 4h, 1D). A trade signal is stronger when "
        "the same direction is confirmed on higher timeframes. Score each "
        "timeframe and require a minimum confluence score before entry.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E7. Adaptive Position Sizing with Kelly Criterion</b>", S_H3))
    story.append(Paragraph(
        "Replace fixed share counts with dynamic Kelly-based sizing. Track win rate "
        "and average win/loss ratio over a rolling window, then compute optimal "
        "position size. Use fractional Kelly (25-50%) to account for estimation "
        "error. This mathematically optimizes capital growth.",
        S_BODY))
    story.append(code_block(
        "def kelly_size(win_rate: float, avg_win: float, avg_loss: float) -> float:\n"
        "    \"\"\"Returns fraction of capital to risk.\"\"\"\n"
        "    if avg_loss == 0:\n"
        "        return 0.0\n"
        "    b = avg_win / abs(avg_loss)  # win/loss ratio\n"
        "    kelly = (win_rate * b - (1 - win_rate)) / b\n"
        "    return max(0.0, min(kelly * 0.25, 0.02))  # 25% Kelly, max 2% risk"))
    story.append(sp(6))

    story.append(Paragraph("<b>E8. Regime Detection with Hidden Markov Models</b>", S_H3))
    story.append(Paragraph(
        "Upgrade regime detection from simple bull/bear classification to an HMM "
        "that identifies market states: trending-up, trending-down, mean-reverting, "
        "high-volatility, low-volatility. Each regime uses different strategy "
        "parameters (wider stops in volatile regimes, tighter in trending).",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E9. Reinforcement Learning for Exit Optimization</b>", S_H3))
    story.append(Paragraph(
        "Train an RL agent to optimize trade exits. Use historical trade data as "
        "the environment: state = (unrealized P&L, time in trade, volatility, volume). "
        "Actions = hold, partial-exit, full-exit. Reward = realized P&L minus "
        "opportunity cost. This learns when to let winners run vs. take profits.",
        S_BODY))
    story.append(PageBreak())

    # C3: Risk Management
    story.append(Paragraph("C3. RISK MANAGEMENT ENHANCEMENTS", S_H2))
    story.append(sp(4))

    story.append(Paragraph("<b>E10. Correlation-Aware Portfolio Risk</b>", S_H3))
    story.append(Paragraph(
        "Before entering a new position, check its correlation with existing "
        "positions. If you're already long 3 tech stocks and a new tech signal fires, "
        "the portfolio is concentrated. Compute rolling correlation matrices and "
        "reject trades that push sector/correlation exposure beyond limits.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E11. Dynamic Stop Loss with ATR</b>", S_H3))
    story.append(Paragraph(
        "Replace fixed stop losses with ATR-based dynamic stops. In high-volatility "
        "periods, stops are wider (to avoid noise stops). In low-volatility periods, "
        "stops are tighter (to protect gains). Use 2x ATR(14) as default, adjustable "
        "by regime.",
        S_BODY))
    story.append(code_block(
        "def compute_stop(entry_price: float, atr: float, direction: str) -> float:\n"
        "    multiplier = 2.0  # adjustable by regime\n"
        "    if direction == \"LONG\":\n"
        "        return entry_price - (atr * multiplier)\n"
        "    else:\n"
        "        return entry_price + (atr * multiplier)"))
    story.append(sp(6))

    story.append(Paragraph("<b>E12. Maximum Drawdown Auto-Halt</b>", S_H3))
    story.append(Paragraph(
        "Implement automatic system halt when drawdown exceeds configured limits. "
        "Track daily, weekly, and overall drawdown. When any limit is breached: "
        "(1) close all positions, (2) enter HALT state, (3) send alert, "
        "(4) require manual re-enable. This is essential for FTMO/prop firm compliance.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E13. Pre-Trade Risk Checklist</b>", S_H3))
    story.append(Paragraph(
        "Before every trade, run a checklist: (a) position size within limits, "
        "(b) daily loss limit not reached, (c) max concurrent positions not exceeded, "
        "(d) no earnings/Fed events in next 2 hours, (e) spread is within acceptable range, "
        "(f) sufficient liquidity. Log each check result for audit trail.",
        S_BODY))
    story.append(PageBreak())

    # C4: Data & Execution
    story.append(Paragraph("C4. DATA & EXECUTION IMPROVEMENTS", S_H2))
    story.append(sp(4))

    story.append(Paragraph("<b>E14. Order Book Depth Analysis</b>", S_H3))
    story.append(Paragraph(
        "If IBKR provides Level 2 data, analyze bid/ask depth before entry. "
        "Large buy walls below current price support longs. Thin order books mean "
        "higher slippage risk. Use this as a filter: skip trades where the order "
        "book suggests insufficient liquidity for your position size.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E15. Smart Order Routing</b>", S_H3))
    story.append(Paragraph(
        "Instead of market orders, use limit orders with intelligent pricing. "
        "For entries: place limit at the bid + 1 tick (for longs), wait up to "
        "N seconds, then escalate to market if unfilled. For exits: use bracket "
        "orders with OCO (one-cancels-other) for stop and target. This reduces "
        "slippage significantly.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E16. Data Quality Scoring</b>", S_H3))
    story.append(Paragraph(
        "Score incoming OHLCV data quality: check for gaps, stale data, extreme "
        "outliers, and source reliability. If data quality drops below threshold, "
        "pause pattern detection rather than trading on bad data. Log quality "
        "scores to identify recurring data issues.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E17. Paper Trading Simulation Mode</b>", S_H3))
    story.append(Paragraph(
        "Build a proper simulation engine that replays historical data through the "
        "full pipeline (pattern detection -> catalyst check -> risk check -> execution). "
        "Track simulated P&amp;L, win rate, max drawdown, Sharpe ratio. Run this "
        "for 30+ days before going live. Currently the cockpit shows hardcoded "
        "fake positions - replace with real simulation results.",
        S_BODY))
    story.append(PageBreak())

    # C5: Monitoring
    story.append(Paragraph("C5. MONITORING & OBSERVABILITY", S_H2))
    story.append(sp(4))

    story.append(Paragraph("<b>E18. Structured Logging with Context</b>", S_H3))
    story.append(Paragraph(
        "Replace plain text logging with structured JSON logs. Include trade_id, "
        "symbol, agent_name, and correlation_id in every log entry. This makes "
        "it possible to trace a single trade's journey through all agents. "
        "Use structlog or python-json-logger.",
        S_BODY))
    story.append(code_block(
        "import structlog\n"
        "logger = structlog.get_logger()\n\n"
        "logger.info(\"trade_signal_detected\",\n"
        "    symbol=\"AAPL\", pattern=\"head_and_shoulders\",\n"
        "    confidence=78.5, timeframe=\"5m\",\n"
        "    trade_id=\"tr_abc123\")"))
    story.append(sp(6))

    story.append(Paragraph("<b>E19. Real-Time Performance Dashboard</b>", S_H3))
    story.append(Paragraph(
        "Build a live dashboard showing: (a) current positions with P&amp;L, "
        "(b) today's trade log with outcomes, (c) system health (agent status, "
        "API latencies, queue depths), (d) risk metrics (drawdown, exposure, "
        "correlation matrix), (e) cumulative equity curve. Use the existing "
        "React frontend with TradingView lightweight-charts.",
        S_BODY))
    story.append(sp(6))

    story.append(Paragraph("<b>E20. Anomaly Detection on System Metrics</b>", S_H3))
    story.append(Paragraph(
        "Monitor system metrics and alert on anomalies: sudden spike in API "
        "latency, unusual number of trade signals, data gaps, memory growth, "
        "queue backlog. Use simple statistical methods (rolling mean + 3 sigma) "
        "or the existing Ollama for LLM-based anomaly description.",
        S_BODY))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PART D: EXECUTION TIMELINE
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("PART D: EXECUTION TIMELINE & PRIORITY MATRIX", S_H1))
    story.append(hr())

    story.append(Paragraph("REMEDIATION SCHEDULE", S_H2))
    story.append(sp(4))

    timeline_table = make_table(
        ["Week", "Phase", "Steps", "Effort", "Risk Reduction"],
        [
            ["Week 1", "Phase 1: Critical Fixes", "Steps 1-6", "High",
             "Prevents crashes & data loss"],
            ["Week 2", "Phase 2: Security", "Steps 7-11", "Medium",
             "Closes security holes"],
            ["Week 3", "Phase 3: Race Conditions", "Steps 12-14", "Medium",
             "Prevents state corruption"],
            ["Week 4", "Phase 4: Logic Bugs", "Steps 15-18", "Medium",
             "Correct trading decisions"],
            ["Week 5", "Phase 5+6: Stubs & Perf", "Steps 19-22", "Medium",
             "System honesty & speed"],
            ["Week 6", "Phase 7+8: Config & Tests", "Steps 23-27", "Medium",
             "Long-term maintainability"],
            ["Week 7", "Phase 9: Build & Deploy", "Steps 28-30", "Low",
             "Production readiness"],
        ],
        col_widths=[0.7*inch, 1.5*inch, 1.3*inch, 0.7*inch, 1.6*inch]
    )
    story.append(timeline_table)
    story.append(sp(12))

    story.append(Paragraph("ENHANCEMENT PRIORITY", S_H2))
    story.append(sp(4))

    enhance_table = make_table(
        ["Priority", "Enhancement", "ID", "Impact", "Effort"],
        [
            ["1 (Do First)", "Real Sentiment Analysis", "E5", "High", "Medium"],
            ["1", "Pre-Trade Risk Checklist", "E13", "High", "Low"],
            ["1", "Maximum Drawdown Auto-Halt", "E12", "Critical", "Low"],
            ["2", "Circuit Breaker Pattern", "E3", "High", "Low"],
            ["2", "Dynamic ATR Stops", "E11", "High", "Low"],
            ["2", "Paper Trading Simulation", "E17", "High", "Medium"],
            ["3", "Multi-Timeframe Confluence", "E6", "High", "Medium"],
            ["3", "Kelly Position Sizing", "E7", "Medium", "Medium"],
            ["3", "Structured Logging", "E18", "Medium", "Low"],
            ["4", "Event-Driven Architecture", "E1", "High", "High"],
            ["4", "Regime Detection (HMM)", "E8", "High", "High"],
            ["4", "Correlation-Aware Risk", "E10", "Medium", "Medium"],
            ["5", "Order Book Analysis", "E14", "Medium", "High"],
            ["5", "Smart Order Routing", "E15", "Medium", "Medium"],
            ["5", "RL Exit Optimization", "E9", "High", "Very High"],
            ["5", "Real-Time Dashboard", "E19", "Medium", "Medium"],
            ["6", "State Machine Lifecycle", "E2", "Medium", "Medium"],
            ["6", "DI Container", "E4", "Medium", "Medium"],
            ["6", "Data Quality Scoring", "E16", "Low", "Low"],
            ["6", "Anomaly Detection", "E20", "Low", "Medium"],
        ],
        col_widths=[0.8*inch, 1.7*inch, 0.5*inch, 0.7*inch, 0.8*inch]
    )
    story.append(enhance_table)
    story.append(sp(12))

    # Final summary box
    story.append(hr())
    story.append(Paragraph("FINAL NOTES", S_H2))
    story.append(sp(4))
    story.append(danger_box(
        "<b>DO NOT trade live until Phase 1 (Steps 1-6) and Phase 2 (Steps 7-11) "
        "are complete.</b> The DMS infinite recursion (C2) alone means your emergency "
        "position flattening can crash under network instability. The bare exception "
        "handlers (C4) mean the system can be silently broken while appearing healthy."))
    story.append(sp(6))
    story.append(warning_box(
        "<b>The stub implementations (M6) are especially deceptive.</b> "
        "mind_observer always returns BULLISH sentiment and CLEAN environment regardless "
        "of actual market conditions. Any trading logic that depends on these signals "
        "is making decisions based on hardcoded lies. Fix these before trusting "
        "the system's intelligence."))
    story.append(sp(6))
    story.append(tip_box(
        "<b>Suggested approach:</b> Complete all 30 remediation steps first (Weeks 1-7). "
        "Then implement enhancements E5, E12, E13 (sentiment, auto-halt, risk checklist). "
        "Run in paper trading mode (E17) for at least 30 days. Only then consider live trading. "
        "This system has strong architectural bones - once the bugs are fixed and stubs "
        "are replaced with real implementations, it can be genuinely powerful."))
    story.append(sp(20))

    story.append(Paragraph(
        "End of Report", make_style("end", fontSize=10, textColor=CLR_TEXT_LIGHT,
                                     alignment=TA_CENTER)))
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        make_style("end2", fontSize=8, textColor=CLR_TEXT_LIGHT, alignment=TA_CENTER)))

    # ── BUILD ───────────────────────────────────────────────────
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    print(f"PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
