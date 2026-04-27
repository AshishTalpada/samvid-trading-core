# pyre-ignore-all-errors[21]
"""
src/dhatu_oracle.py - Dhatu Omniscience Global Knowledge Graph
"""

import asyncio
import json
import logging  # pyre-ignore[21]
import math
import os
import re
import time
from dataclasses import dataclass, field  # pyre-ignore[21]
from datetime import datetime, timedelta  # pyre-ignore[21]
from typing import TYPE_CHECKING, Any, Dict  # pyre-ignore[21]

import httpx  # pyre-ignore[21]
import numpy as np  # pyre-ignore[21]
import websockets

from api_cache import TTLCache  # pyre-ignore[21]
from database_security import Vault  # pyre-ignore[21]
from telegram_alerts import send_telegram_alert

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus  # pyre-ignore[21]

from datetime import timezone

logger = logging.getLogger(__name__)


def _short_exc(exc: BaseException, limit: int = 180) -> str:
    msg = str(exc)
    if len(msg) <= limit:
        return msg
    stop_idx: int = limit - 3
    return msg[:stop_idx] + "..."  # pyre-ignore[6]


# =============================================================================
# 6-VERTICAL VARIABLE TAXONOMY
# =============================================================================

GEOPOLITICAL_KEYWORDS: list[str] = [
    "diplomacy",
    "sanctions",
    "embargo",
    "treaty",
    "alliance",
    "NATO",
    "UN",
    "G7",
    "BRICS",
    "EU",
    "IMF",
    "sovereignty",
    "conflict",
    "tension",
    "escalation",
    "deescalation",
    "war",
    "invasion",
    "military",
    "defense",
    "airstrike",
    "missile",
    "drone",
    "cyberattack",
    "terrorism",
    "insurgency",
    "ceasefire",
    "truce",
    "peace",
    "instability",
    "coup",
    "regime",
    "election",
    "protest",
    "strike",
    "unrest",
    "demonstration",
    "reform",
    "negotiation",
    "veto",
    "summit",
    "rivalry",
    "dominance",
]

MACRO_KEYWORDS: list[str] = [
    "policy",
    "regulation",
    "legislation",
    "tariff",
    "import",
    "export",
    "restriction",
    "blockade",
    "crisis",
    "collapse",
    "recession",
    "depression",
    "inflation",
    "deflation",
    "stagflation",
    "growth",
    "slowdown",
    "GDP",
    "unemployment",
    "output",
    "consumption",
    "demand",
    "supply",
    "stimulus",
    "subsidy",
    "tax",
    "deficit",
    "budget",
    "treasury",
    "bond",
    "yield",
    "interest",
    "rate",
    "hike",
    "cut",
    "easing",
    "tightening",
    "QE",
    "QT",
    "FederalReserve",
    "ECB",
    "BOJ",
    "PBOC",
    "RBI",
    "dovish",
    "hawkish",
]

PHYSICAL_KEYWORDS: list[str] = [
    "oil",
    "crude",
    "gasoline",
    "diesel",
    "LNG",
    "gas",
    "power",
    "grid",
    "blackout",
    "renewable",
    "solar",
    "wind",
    "nuclear",
    "uranium",
    "coal",
    "gold",
    "silver",
    "copper",
    "aluminum",
    "nickel",
    "lithium",
    "steel",
    "iron",
    "wheat",
    "corn",
    "soybean",
    "rice",
    "sugar",
    "coffee",
    "cocoa",
    "livestock",
    "cattle",
    "poultry",
    "fertilizer",
    "harvest",
    "drought",
    "flood",
    "hurricane",
    "cyclone",
    "typhoon",
    "storm",
    "wildfire",
    "earthquake",
    "volcano",
    "climate",
    "ElNino",
    "LaNina",
    "emissions",
    "carbon",
    "pollution",
    "ESG",
]

CORPORATE_KEYWORDS: list[str] = [
    "earnings",
    "revenue",
    "profit",
    "loss",
    "margin",
    "guidance",
    "surprise",
    "beat",
    "miss",
    "valuation",
    "PE",
    "ratio",
    "dividend",
    "buyback",
    "issuance",
    "IPO",
    "merger",
    "acquisition",
    "takeover",
    "spin-off",
    "restructuring",
    "layoffs",
    "hiring",
    "expansion",
    "partnership",
    "monopoly",
    "antitrust",
    "lawsuit",
    "litigation",
    "settlement",
    "fine",
    "compliance",
    "audit",
    "fraud",
    "scandal",
    "corruption",
    "CEO",
    "CFO",
    "governance",
]

TECH_KEYWORDS: list[str] = [
    "AI",
    "robotics",
    "automation",
    "machinelearning",
    "semiconductor",
    "chip",
    "shortage",
    "fabrication",
    "industrial",
    "patent",
    "startup",
    "venture",
    "liquidity",
    "leverage",
    "mortgage",
    "housing",
    "realestate",
    "urbanization",
    "infrastructure",
    "supplychain",
    "procurement",
    "outsourcing",
    "localization",
    "digitization",
    "cybersecurity",
    "hacking",
    "breach",
    "ransomware",
    "malware",
    "phishing",
    "encryption",
    "firewall",
    "cloud",
    "datacenter",
    "server",
    "5G",
    "satellite",
    "space",
    "defenseindustry",
    "aviation",
    "pandemic",
    "virus",
    "vaccine",
    "healthcare",
    "pharma",
    "biotech",
    "trial",
]

MARKET_MECHANICS_KEYWORDS: list[str] = [
    "volatility",
    "VIX",
    "spike",
    "crash",
    "rally",
    "bull",
    "bear",
    "correction",
    "breakout",
    "trend",
    "reversal",
    "momentum",
    "resistance",
    "support",
    "liquiditycrunch",
    "selloff",
    "speculation",
    "arbitrage",
    "hedging",
    "derivatives",
    "options",
    "futures",
    "swaps",
    "forex",
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "CNY",
    "INR",
    "CAD",
    "AUD",
    "devaluation",
    "peg",
    "float",
    "systemic",
    "contagion",
    "spillover",
    "shock",
    "catalyst",
    "blackswans",
    "tailrisk",
]


# =============================================================================
# CAUSATION GRAPH (Gemini Output Structure)
# =============================================================================


@dataclass
class CausationEdge:
    """A single causal link between two global factors."""

    source: str  # e.g. "LaNina (Weather)"
    effect: str  # e.g. "Soybean drought (Agriculture)"
    mechanism: str  # e.g. "Rainfall deficit reduces yield by ~30%"
    confidence: float  # 0.0-1.0


@dataclass
class CausationGraph:
    """
    Condensed causal map produced by Gemini 2.0 Flash.
    Represents the daily synthesis of all 6 ingestion verticals.
    """

    edges: list[CausationEdge] = field(default_factory=list)
    dominant_theme: str = "NEUTRAL"  # e.g. "Supply friction peak"
    macro_bias: str = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL
    uncertainty_score: float = 0.5  # 0=certainty, 1=maximum uncertainty
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def certainty(self) -> float:
        """Return the inverse of the uncertainty score (0.0 to 1.0)."""
        return round(1.0 - self.uncertainty_score, 3)


# =============================================================================
# DHATU ORACLE STATE (Claude Output)
# =============================================================================

# Dhatu state → Agent B action protocol mapping
DHATU_PROTOCOL_MAP: dict[str, dict[str, Any]] = {
    "Viyoga": {
        "dhatu": "Viyoga (Separation)",
        "trigger": "BRICS alliance + AI chip ban + USD devaluation",
        "action": "FLATTEN",
        "detail": "Sell all Equities. Rotate into Gold/Uranium commodities.",
        "risk_modifier": 0.0,
    },
    "Vriddhi": {
        "dhatu": "Vriddhi (Growth)",
        "trigger": "Fed cuts rates + IPO expansion + robust grid",
        "action": "MAX_RISK",
        "detail": "Long QQQ/SPY, extend profit targets, leverage up.",
        "risk_modifier": 1.5,
    },
    "Kshaya": {
        "dhatu": "Kshaya (Decay)",
        "trigger": "Ransomware on ports + semiconductor shortage + inflation surge",
        "action": "SHORT_HEDGE",
        "detail": "Aggressive shorting on retail/industrial indices.",
        "risk_modifier": 0.25,
    },
    "Abhava": {
        "dhatu": "Abhava (Absence)",
        "trigger": "Pandemic + housing collapse + VIX spike",
        "action": "CASH",
        "detail": "100% Cash. Capital preservation absolute lockdown.",
        "risk_modifier": 0.0,
    },
    "Samyoga": {
        "dhatu": "Samyoga (Conjunction)",
        "trigger": "Multiple bullish catalysts aligning",
        "action": "AGGRESSIVE_LONG",
        "detail": "Full position, all pattern types active.",
        "risk_modifier": 1.25,
    },
    "Sthira": {
        "dhatu": "Sthira (Stable)",
        "trigger": "Low volatility, range-bound macro",
        "action": "NORMAL",
        "detail": "Standard sizing, mean-reversion focus.",
        "risk_modifier": 1.0,
    },
    "Chala": {
        "dhatu": "Chala (Volatile)",
        "trigger": "High VIX, directional uncertainty",
        "action": "REDUCE",
        "detail": "50% size reduction, widen stops.",
        "risk_modifier": 0.5,
    },
    "Sthiti": {
        "dhatu": "Sthiti (Persistence)",
        "trigger": "Continuation of prior macro state",
        "action": "HOLD",
        "detail": "Maintain current posture.",
        "risk_modifier": 0.95,
    },
}


@dataclass
class OracleState:
    """
    The final output of the Dhatu Oracle — the global market state
    distilled into a single actionable framework for Agent B.
    """

    dhatu_state: str  # e.g. "Vriddhi"
    action_protocol: str  # e.g. "MAX_RISK"
    risk_modifier: float  # Multiplicative modifier for position sizing
    causation_summary: str  # LLM-generated narrative
    confidence: float  # 0.0-1.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_graph: CausationGraph | None = None

    @property
    def is_fresh(self) -> bool:
        """Oracle state is considered fresh for 10 minutes (GAP-32 Hardening)."""
        now = datetime.now(timezone.utc)
        return (now - self.generated_at) < timedelta(minutes=10)


# =============================================================================
# NEURAL NEWS INTELLIGENCE (AGENT B - THE READER)
# =============================================================================

class NewsHarvester:
    """
    Consolidated News Intelligence.
    Reads headlines from multiple sources and distills them into sentiment signals.
    """

    def __init__(self, bus: "SharedIntelligenceBus | None" = None) -> None:
        self.bus = bus
        # Adjusted for 4GB VRAM (GTX 1050) - phi3:mini fits perfectly
        self._local_model = Vault.get("OLLAMA_MODEL_MACRO", "phi3:mini") or "phi3:mini"
        self.finnhub_key = Vault.get("FINNHUB_API_KEY") or Vault.get("FINNHUB_KEY")
        self._running = False
        self._last_headlines = set()
        if self.finnhub_key:
            logger.info("NewsHarvester: Finnhub Imperial Credentials HYDRATED.")
        else:
            logger.warning("NewsHarvester: Finnhub Key MISSING. General market news feed will be offline.")

    async def _distill_headline(self, headline: str) -> dict:
        """The 'Reading' logic: Uses heuristic scoring and LLM prioritization."""
        impact = 0.0
        sentiment = 0.0

        # High-Impact keywords for fast heuristic scoring
        IMPACT_KEYWORDS = {
            "FED": 0.8, "CPI": 0.7, "FOMC": 0.8, "POWELL": 0.7,
            "HALT": 0.9, "CRASH": 0.9, "WAR": 0.8, "EXPLOSION": 0.8,
            "BREAKING": 0.5, "ALERT": 0.5
        }

        for k, score in IMPACT_KEYWORDS.items():
            if k in headline.upper():
                impact = max(impact, score)

        # Simple sentiment heuristic (Temporary until LLM synthesis)
        BULL_WORDS = [
            "BEAT", "UPGRADE", "RAISE", "POSITIVE", "GROWTH", "WIN", "SURGE", "PROFIT",
            "BULLISH", "SUCCESS", "EXPAND", "BUY", "OUTPERFORM", "RECOVERY", "BOOM", "HIKE",
            "SHORT SQUEEZE" # GAP-25 FIX: Short Squeeze is explicitly Bullish
        ]
        BEAR_WORDS = [
            "MISS", "DOWNGRADE", "LOWER", "NEGATIVE", "FALL", "LOSS", "DROP", "PLUNGE",
            "BEARISH", "FAILURE", "SHRINK", "SELL", "UNDERPERFORM", "CRASH", "SLUMP", "CUT"
        ]

        for w in BULL_WORDS:
            if w in headline.upper(): sentiment += 0.25
        for w in BEAR_WORDS:
            if w in headline.upper(): sentiment -= 0.25

        return {"headline": headline, "impact": impact, "sentiment": max(-1.0, min(1.0, sentiment))}

    async def run(self) -> None:
        self._running = True
        logger.info("NewsHarvester: Neural Reading Hub active.")

        # Samvid v1.0-beta-beta-beta: Persistent Client for connection pooling
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
            while self._running:
                try:
                    # Source 1: Finnhub (Market News)
                    if self.finnhub_key:
                        self.status_summary = "Harvesting Headlines"
                        resp = await client.get(
                            f"https://finnhub.io/api/v1/news?category=general&token={self.finnhub_key}"
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            processed = 0
                            # GAP-27: API Bloat - Limit processing to top 10 items
                            for item in data[:10]:
                                    h = str(item.get("headline", ""))
                                    s_text = str(item.get("summary", ""))
                                    full_text = f"{h} {s_text}".upper()

                                    # GAP-236 FIX: Scan both Headline and Body (Summary)
                                    is_dot = any(k.upper() in full_text for k in GEOPOLITICAL_KEYWORDS + MACRO_KEYWORDS)
                                    if (is_dot) and h not in self._last_headlines and processed < 5:
                                        self._last_headlines.add(h)
                                        processed += 1
                                        distilled = await self._distill_headline(f"{h} | {s_text}")

                                        # ── NEURAL DELTA DETECTION (SE-11 Port) ──
                                        # Capture shift from 'last sentiment' to 'this headline'
                                        if distilled["impact"] > 0.6:
                                             self.status_summary = f"Synthesizing {h[:15]}..."
                                             logger.info(f"📰 HIGH IMPACT: {h} (Sentiment Shift: {distilled['sentiment']})")

                                        if self.bus:
                                            await self.bus.publish("news.hft", {
                                                "source": "Finnhub", "headline": h,
                                                "summary": s_text,
                                                "impact": distilled["impact"], "sentiment": distilled["sentiment"],
                                                "timestamp": datetime.now(timezone.utc).isoformat()
                                            })

                            self.status_summary = f"Monitoring {len(data)} Feeds"
                        else:
                            logger.error(f"NewsHarvester: API Error {resp.status_code} from Finnhub.")

                    if len(self._last_headlines) > 1000:
                        # Defensive sorting: ensure we only sort strings to prevent TypeError
                        current = sorted([str(x) for x in self._last_headlines])
                        self._last_headlines = set(current[-200:])

                    await asyncio.sleep(60) # Poll every minute

                except Exception as e:
                    logger.error(f"🚨 NewsHarvester: Neural Hub failure: {e}")
                    await asyncio.sleep(60)

# =============================================================================
# TRADINGVIEW NEWS SCENT (THE IMPERIAL FEED)
# =============================================================================

class TVNewsScent:
    """
    Sub-millisecond News 'Scent' via TradingView WebSocket.
    Reverse-engineered protocol for High-Frequency headline ingestion.
    """

    def __init__(self, bus: "SharedIntelligenceBus | None" = None) -> None:
        self.url = "wss://data.tradingview.com/socket.io/websocket"
        self.bus = bus
        self.session_id = f"ns_{os.urandom(6).hex()}"
        self._running = False
        self._ws = None

    def _format_message(self, data: dict) -> str:
        """TradingView ~m~ framing."""
        msg = json.dumps(data, separators=(",", ":"))
        return f"~m~{len(msg)}~m~{msg}"

    def _parse_messages(self, raw_data: str) -> list[dict]:
        """
        Decode TradingView ~m~ framed messages.
        Formula: ~m~length~m~JSON
        """
        results = []
        try:
            # Samvid v1.0-beta-beta-beta: Robust length-prefixed parsing (replaces brittle split)
            ptr = 0
            while ptr < len(raw_data):
                if not raw_data[ptr:].startswith('~m~'):
                    break

                # Find the second ~m~
                end_len_idx = raw_data.find('~m~', ptr + 3)
                if end_len_idx == -1:
                    break

                msg_len = int(raw_data[ptr + 3 : end_len_idx])
                start_json = end_len_idx + 3
                end_json = start_json + msg_len

                json_str = raw_data[start_json:end_json]
                try:
                    results.append(json.loads(json_str))
                except json.JSONDecodeError:
                    pass

                ptr = end_json
        except Exception:
            pass
        return results

    async def run(self) -> None:
        """Main WebSocket loop."""
        self._running = True
        logger.info("TVNewsScent: Initiating Imperial Scent Connection...")

        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        while self._running:
            try:
                # Samvid v1.0-beta-beta-beta: Explicit Handshake Mapping
                target_url = self.url
                target_headers = headers
                async with websockets.connect(
                    target_url,
                    additional_headers=target_headers,
                    open_timeout=40.0,  # Increased for G3 network stability
                    ping_interval=10,
                    ping_timeout=10
                ) as ws:
                    self._ws = ws
                    # 1. Initialize News Session
                    await ws.send(self._format_message({"m": "news_create_session", "p": [self.session_id]}))
                    # 2. Subscribe to Global Feed (or specific targets)
                    # Note: 'news_feed' handles the streaming of headlines
                    await ws.send(self._format_message({"m": "news_feed", "p": [self.session_id, "news_feed:1:1:1:1", "ALL:ALL"]}))

                    logger.info("✓ TVNewsScent: Neural Scent Feed established (TradingView WS).")

                    async for message in ws:
                        if isinstance(message, str):
                            # Handle Heartbeats (~h~)
                            if message.startswith("~h~"):
                                await ws.send(message)
                                continue

                            msgs = self._parse_messages(message)
                            for msg in msgs:
                                if msg.get("m") == "news_item":
                                    p = msg.get("p", [])
                                    if len(p) > 1 and isinstance(p[1], dict):
                                        item = p[1]
                                        headline = item.get("headline", "")
                                        source = item.get("source", "UNKNOWN")

                                        if headline:
                                            logger.info(f"📰 TV_SCENT: [{source}] {headline}")
                                            # Broadcast to the machine's nervous system
                                            if self.bus:
                                                await self.bus.publish("news.hft", {
                                                    "source": "TradingView_WS",
                                                    "headline": headline,
                                                    "provider": source,
                                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                                })
            except Exception as e:
                logger.error(f"⚠️ TVNewsScent: Neural Scent blip (Check Origin/Proxy): {e}")

            # Samvid v1.0-beta-beta-beta: Mandatory Neural Cooling (Prevents machine-gun reconnects)
            # Replaces the unstable fixed sleep inside the except block.
            await asyncio.sleep(15)

# =============================================================================
# DHATU ORACLE — THE GLOBAL BRAIN
# =============================================================================


class DhatuOracle:
    """
    Multi-stage LLM pipeline that synthesizes 500+ global variables into
    a single Dhatu state and risk protocol for the execution engine.

    Pipeline:
      Step 1: Ingest from 6 vertical sources (news, central banks, etc.)
      Step 2: Gemini 2.0 Flash builds the Causation Graph
      Step 3: Claude 3.5 Opus maps graph → Dhatu State
      Step 4: Publish OracleState to Agent B every ~15 minutes

    Requires:
      GOOGLE_API_KEY  (for Gemini)
      ANTHROPIC_API_KEY (for Claude)
    """

    def __init__(
        self,
        google_api_key: str = "",
        anthropic_api_key: str = "",
        ollama_base_url: str = "http://127.0.0.1:11434/v1",
        ollama_model: str = "llama3",
        gemini_model: str = "gemini-2.0-flash",
        bus: "SharedIntelligenceBus | None" = None,
    ) -> None:
        self._google_key = google_api_key
        self._anthropic_key = anthropic_api_key
        self._current_state: OracleState | None = None
        self._refresh_interval_minutes = 10 # Reduced for GAP-32
        self._bus: SharedIntelligenceBus | None = bus
        _ob = (ollama_base_url or "http://127.0.0.1:11434/v1").rstrip("/")
        if not _ob.endswith("/v1"):
            _ob = f"{_ob}/v1"
        self._ollama_base_url = _ob
        self._local_model = ollama_model
        self._gemini_model = gemini_model

        # GAP-32: Interruptible refresh for 'Flash' events
        self._flash_event = asyncio.Event()
        self._flash_keywords = {"CRASH", "HALT", "WAR", "EXPLOSION", "LIQUIDATION", "PANIC", "FLASH", "CIRCUIT"}
        self._last_flash_time = 0.0 # Throttler

        # GAP-70: Anti-Injection Sanitizer
        self._forbidden_neural = ["IGNORE ALL", "SYSTEM:", "USER:", "PREVIOUS INSTRUCTIONS", "SETTING:"]

        # TTL caches to prevent 429 rate-limit errors
        self._ticker_cache = TTLCache(default_ttl=300.0, max_size=200)  # 5min for ticker data
        self._graph_cache = TTLCache(default_ttl=600.0, max_size=50)  # 10min for LLM graphs
        self._db_path = "data/trading.db"
        self._init_db()
        self._load_persisted_state()
        self._news_scent = TVNewsScent(bus=bus)
        self._news_harvester = NewsHarvester(bus=bus)
        # Samvid v1.0-beta-beta-beta: Live News Intelligence Buffer (Captures all dots)
        # Samvid v1.0-beta-beta-beta: Live Intelligence Buffers
        self._news_buffer: list[str] = []
        self._macro_buffer: list[str] = []
        self._flow_buffer: list[str] = []
        if self._bus:
            self._bus.on("news.hft", self._on_news_received)
            self._bus.on("news.event", self._on_news_received)
            self._bus.on("macro.impact", self._on_macro_received)
            self._bus.on("institutional.flow", self._on_flow_received)
        self._background_tasks: list[asyncio.Task] = []

        # --- BAYESIAN REWARD MECHANISM (Samvid v1.0-beta-beta-beta Native Integration) ---
        from bayesian_oracle import BayesianOracle
        self._bayesian_oracle = BayesianOracle()

        # Samvid v1.0-beta-beta-beta: Persistent Ollama client — eliminates per-call AsyncClient alloc (~30 MB each)
        self._ollama_client: "httpx.AsyncClient | None" = None

    async def _on_news_received(self, data: dict) -> None:
        """Capture news headlines into the short-term memory buffer (Hardened GAP-70/32)."""
        h_raw = data.get("headline")
        s = data.get("source", "UNKNOWN")
        if not h_raw: return

        # GAP-70 FIX: Neural Injection Shield
        h_up = h_raw.upper()
        h = h_raw
        if any(f in h_up for f in self._forbidden_neural):
            logger.warning(f"🛡️ DHATU INJECTION SHIELD: Redacted malicious news headline from {s}")
            h = f"[REDACTED_INJECTION] {h_raw[:20]}..."
            h_up = h.upper()

        if h:
            self._news_buffer.append(f"[{s}] {h}")
            if len(self._news_buffer) > 100:
                self._news_buffer.pop(0)

            # GAP-32: Trigger 'Flash Refresh' with Throttle
            found_k = [k for k in self._flash_keywords if k in h_up]
            if found_k:
                # GAP-80 Hardening: Negation awareness (Semantic Drift Protection)
                negators = ["NOT ", "NO ", "NEVER ", "FALSE ", "DENIES ", "REJECTS ", "UNLIKELY "]
                is_negated = any(neg + k in h_up for k in found_k for neg in negators)

                now = time.time()
                # 5-minute cooldown between flashes to prevent LLM/Budget burnout
                if not is_negated and (now - self._last_flash_time > 300):
                    logger.warning(f"🏛️ DHATU FLASH TRIGGER: critical news detected: '{h}'")
                    self._last_flash_time = now
                    self._flash_event.set()

    async def _on_macro_received(self, data: dict) -> None:
        """Capture macro impact signals into the Oracle buffer."""
        impact = data.get("impact", "NEUTRAL")
        reason = data.get("reason", "N/A")
        self._macro_buffer.append(f"[MACRO_IMPACT] {impact}: {reason}")
        if len(self._macro_buffer) > 20: self._macro_buffer.pop(0)

    async def _on_flow_received(self, data: dict) -> None:
        """Capture institutional flow signals into the Oracle buffer."""
        bias = data.get("flow_bias", "NEUTRAL")
        sym = data.get("symbol", "N/A")
        det = data.get("detail", "")
        self._flow_buffer.append(f"[INST_FLOW] {sym} {bias}: {det}")
        if len(self._flow_buffer) > 20: self._flow_buffer.pop(0)

    def calculate_spread_tension(self, bid: float, ask: float, volume: float) -> float:
        """
        Calculates the SE-11 'Sub-Atomic Tension' (Entropy-Zero).
        Measures the exponential compression of the bid-ask spread relative to incoming volume.
        High Tension = Imminent Liquidity Collapse (Breakout/Flush).
        """
        spread = abs(ask - bid)
        if spread <= 0:
             # Inverted spread or zero spread = MAXIMUM TENSION
             return 100.0

        # TENSION = VOLUME / SPREAD^2 (Sovereign Paradox)
        # As spread tightens, tension explodes exponentially, signaling institutional exhaustion.
        tension = volume / (spread ** 2)

        # Normalize to a 0-100 logarithmic scale
        # log10(1) = 0, log10(1,000,000) = 6
        normalized_tension = min(100.0, 15.0 * math.log10(max(1.0, tension)))
        return normalized_tension

    def _init_db(self) -> None:
        """Ensure the system_state table exists."""
        import sqlite3

        try:
            with sqlite3.connect(self._db_path, timeout=60.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout = 60000;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        except Exception as e:
            logger.error(f"DhatuOracle: Failed to init DB: {e}")

    def _persist_state(self, state: OracleState) -> None:
        """Save current OracleState to database."""
        import sqlite3

        try:
            state_data = {
                "dhatu_state": state.dhatu_state,
                "action_protocol": state.action_protocol,
                "risk_modifier": state.risk_modifier,
                "causation_summary": state.causation_summary,
                "confidence": state.confidence,
                "generated_at": state.generated_at.isoformat(),
            }
            with sqlite3.connect(self._db_path, timeout=60.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout = 60000;")
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("oracle_state", json.dumps(state_data), datetime.now(timezone.utc)),
                )
            logger.debug("DhatuOracle: State persisted to DB")
        except Exception as e:
            logger.error(f"DhatuOracle: Failed to persist state: {e}")

    def _load_persisted_state(self) -> None:
        """Load last OracleState from database."""
        import sqlite3

        try:
            with sqlite3.connect(self._db_path, timeout=60.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout = 60000;")
                cursor = conn.execute("SELECT value FROM system_state WHERE key = 'oracle_state'")
                row = cursor.fetchone()
                if row:
                    data = json.loads(row[0])
                    self._current_state = OracleState(
                        dhatu_state=data["dhatu_state"],
                        action_protocol=data["action_protocol"],
                        risk_modifier=data["risk_modifier"],
                        causation_summary=data["causation_summary"],
                        confidence=data["confidence"],
                        generated_at=datetime.fromisoformat(data["generated_at"]),
                    )
                    logger.info(
                        f"DhatuOracle: Recovered persisted state: {self._current_state.dhatu_state}"
                    )
        except Exception as e:
            logger.debug(f"DhatuOracle: No persisted state found or failed to load: {e}")

    # ------------------------------------------------------------------
    # Public API — consumed by Agent B
    # ------------------------------------------------------------------

    def get_current_state(self) -> OracleState | None:
        """Return the current Oracle state (or None if not yet initialised)."""
        return self._current_state

    def get_risk_modifier(self) -> float:
        """Return the global risk modifier (safe default: 1.0)."""
        state = self._current_state
        if state is not None and state.is_fresh:
            return float(state.risk_modifier)
        return 1.0

    def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized consensus evaluation for Samvid v1.0-beta-beta-beta.
        Provides the Dhatu Oracle's macro-perspective vote.
        """
        modifier = self.get_risk_modifier()
        dhatu_state = self.get_dhatu_state()
        confidence = 0.5
        if self._current_state:
            confidence = self._current_state.confidence

        # Macro Veto Logic: Extreme conditions trigger automatic VETO
        vote = "YES"
        reason = f"Macro State: {dhatu_state} (Mod: {modifier:.2f})"
        if self._current_state:
            reason += f" | {self._current_state.causation_summary}"


        # --- PREDATOR RE-WIRE: PROPORTIONAL SCALING (v1.0-beta-beta-beta) ---
        # Instead of blocking everything below 0.70, we allow the system to strike with
        # reduced size. We only VETO in extreme 'Abhava' or Liquidity Collapse.
        if modifier < 0.40:
            vote = "NO"
            reason = f"VETO: Absolute Macro Chaos! Modifier {modifier:.2f} < 0.40 Critical Floor."
        elif modifier < 0.70:
            reason = f"CAUTION: High Risk Scaling ({modifier:.2f}x). Strikes permitted at reduced size."

        return {
            "agent": "Dhatu_Oracle",
            "vote": vote,
            "confidence": confidence,
            "signal_strength": modifier,
            "risk_flag": modifier < 0.85,
            "reason": reason,
            "dhatu_state": dhatu_state,
            "risk_modifier": modifier,
            "timestamp": context.get("timestamp", datetime.now(timezone.utc).isoformat())
        }

    def get_dhatu_state(self) -> str:
        """Return current Dhatu state name."""
        state = self._current_state
        if state is not None and state.is_fresh:
            return str(state.dhatu_state)
        return "Sthiti"  # Persistence — neutral default

    # ------------------------------------------------------------------
    # Continuous Refresh Loop
    # ------------------------------------------------------------------

    async def run_continuous(self) -> None:
        """Main Oracle loop — refreshes state every ~15 minutes."""
        logger.info("DhatuOracle: Starting continuous global synthesis loop")

        # --- Launch News Intelligence (with task tracking to avoid leaks) ---
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        self._background_tasks.clear()

        self._background_tasks.append(asyncio.create_task(self._news_scent.run()))
        self._background_tasks.append(asyncio.create_task(self._news_harvester.run()))

        # --- FAST STARTUP: Use persisted state if available to avoid token burn ---
        if self._current_state is not None:
            logger.info(
                f"DhatuOracle: Using cached state {self._current_state.dhatu_state} for startup."
            )
        else:
            # Only run if we have no state at all
            state = await self._full_synthesis_cycle()
            if state:
                self._current_state = state
                self._persist_state(state)

        while True:
            try:
                # ── HEARTBEAT PULSE (Samvid v1.0-beta-beta-beta) ──
                # If we have a bus with a DMS registered, record our existence
                if self._bus and hasattr(self._bus, 'dms') and self._bus.dms:
                    self._bus.dms.record_heartbeat()

                # GAP-32: Interruptible Sleep (Normal refresh OR Flash wake-up)
                try:
                    await asyncio.wait_for(
                        self._flash_event.wait(),
                        timeout=self._refresh_interval_minutes * 60
                    )
                    logger.warning("DhatuOracle: FLASH REFRESH triggered by neural scent.")
                except asyncio.TimeoutError:
                    pass # Normal timed refresh

                self._flash_event.clear()

                # If flash/manual refresh, clear caches to force raw re-ingestion
                await self._ticker_cache.clear()
                await self._graph_cache.clear()

                state = await self._full_synthesis_cycle()
                if state:
                    self._current_state = state
                    self._persist_state(state)
                    logger.info(
                        f"DhatuOracle: {state.dhatu_state} "
                        f"[{state.action_protocol}] "
                        f"modifier={state.risk_modifier:.2f} "
                        f"confidence={state.confidence:.0%}"
                    )

                # ── Broadcast Latest State for all Subscribers ──
                if self._bus is not None:
                    # 1. Hard-stop signal for Abhava (capital preservation) or
                    # Viyoga (separation / sell all equities).
                    if state.dhatu_state in ("Abhava", "Viyoga"):
                        await self._bus.publish(
                            "oracle.freeze",
                            {
                                "dhatu": state.dhatu_state,
                                "reason": state.causation_summary,
                            },
                        )
                        await send_telegram_alert(
                            f"❄️ *ORACLE FREEZE: {state.dhatu_state}*\n"
                            f"Reason: {state.causation_summary}"
                        )
                        logger.warning(f"DhatuOracle: FREEZE published — {state.dhatu_state}")

                    # 2. Universal state update for subscribers (ALWAYS publish)
                    await self._bus.publish(
                        "oracle.state",
                        {
                            "dhatu": state.dhatu_state,
                            "action": state.action_protocol,
                            "modifier": state.risk_modifier,
                            "confidence": state.confidence,
                            "theme": state.source_graph.dominant_theme if state.source_graph else "NEUTRAL",
                            "certainty": state.source_graph.certainty if state.source_graph else 0.5,
                            "summary": state.causation_summary,
                        },
                    )
                    # Notify User of Regime Shift
                    await send_telegram_alert(
                        f"🏛️ *REGIME UPDATE: {state.dhatu_state}*\n"
                        f"Action: {state.action_protocol}\n"
                        f"Risk Multiplier: {state.risk_modifier:.2f}\n"
                        f"Summary: {state.causation_summary[:200]}..."
                    )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"DhatuOracle synthesis cycle failed: {e}", exc_info=True)
                # Wait before retry on failure
                await asyncio.sleep(60)

    # ------------------------------------------------------------------
    # Stage 1: Ingestion
    # ------------------------------------------------------------------

    async def _fetch_yf_ticker_data(self, symbol: str, name: str) -> list[str]:
        """Helper to fetch latest price, change %, and latest news for a given ticker."""
        try:
            import yfinance as yf  # pyre-ignore[21]

            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, yf.Ticker, symbol)

            # Fetch 2 days to get change percent
            df = await loop.run_in_executor(
                None,
                lambda t=ticker: t.history(period="5d", interval="1d"),  # type: ignore
            )

            snippets = []
            if not df.empty and len(df) >= 2:
                prev_close = float(df["Close"].iloc[-2])
                current_close = float(df["Close"].iloc[-1])
                pct_change = ((current_close - prev_close) / prev_close) * 100.0
                tag = ""
                if pct_change > 0.5: tag = f"{symbol}_UP"
                elif pct_change < -0.5: tag = f"{symbol}_DOWN"

                # Special mapping for Macro logic
                macro_tag = ""
                if symbol == "^TNX": macro_tag = "YIELD_UP" if pct_change > 0.5 else ("YIELD_DOWN" if pct_change < -0.5 else "")
                elif symbol == "QQQ": macro_tag = "NASDAQ_UP" if pct_change > 0.5 else ("NASDAQ_DOWN" if pct_change < -0.5 else "")

                snippets.append(
                    f"{name} ({symbol}): {current_close:.2f} (change: {pct_change:+.2f}%) {tag} {macro_tag}"
                )

            # Fetch recent news
            news = await loop.run_in_executor(None, lambda t=ticker: t.news)  # type: ignore
            if news and isinstance(news, list):
                for item in [news[i] for i in range(min(2, len(news)))]:
                    title = item.get("title", "")
                    if title:
                        logger.info(f"📰 YF_ORACLE: [{name}] {title}")
                        snippets.append(f"NEWS [{name}]: {title}")

            # Samvid v1.0-beta-beta-beta: Explicitly free Ticker to release internal HTTP session + cached DFs
            del ticker
            del df

            return snippets
        except Exception as e:
            logger.debug(f"Failed to fetch yf data for {symbol}: {e}")
            return []

    async def _ingest_geopolitical(self) -> list[str]:
        """
        Ingest geopolitical signals using diverse proxies.
        """
        logger.debug("DhatuOracle: Ingesting geopolitical data...")
        proxies = [
            ("ITA", "Aerospace & Defense"),
            ("GLD", "Gold (Safe Haven)"),
            ("XLE", "Energy/Oil Conflict"),
            ("TLT", "Long-Term Treasury (Risk-Off)")
        ]
        results = []
        for sym, name in proxies:
            r = await self._ticker_cache.get_or_fetch(
                f"geo_{sym}", lambda s=sym, n=name: self._fetch_yf_ticker_data(s, n), ttl=300
            )
            results.extend(r or [])
        return results

    async def fetch_benchmark_price(self, symbol: str) -> float | None:
        """Helper to fetch a fast 'Reality Check' price from yfinance."""
        try:
            import yfinance as yf
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            # Use fast info lookup
            info = await asyncio.to_thread(lambda: ticker.fast_info)
            return float(info['last_price'])
        except Exception:
            return None

    async def get_last_price(self, symbol: str) -> float | None:
        """Fetch the latest price using the internal TTL cache."""
        try:
            # Check geo/macro/etc caches first
            for category in ["geo", "macro", "phys", "corp", "tech", "mech"]:
                cached = await self._ticker_cache.get(f"{category}_{symbol}")
                if cached and isinstance(cached, list) and len(cached) > 0:
                    # Parse "Name (SYM): 123.45 (change: +1.2%)"
                    match = re.search(r":\s*([\d\.]+)", cached[0])
                    if match:
                        return float(match.group(1))
            return None
        except Exception:
            return None

    async def fetch_macro_snapshot(self) -> dict[str, Any] | None:
        """
        Synthesizes macro signals into a structured dictionary. (GAP-28 FIX)
        Returns None if no signals are available to prevent 'Ghosting' (treating empty as safe).
        """
        logger.debug("DhatuOracle: Compiling macro snapshot...")
        signals = await self._ingest_macro()
        if not signals:
            logger.warning("DhatuOracle: EMPTY macro snapshot detected. Returning None to trigger safety fallback.")
            return None

        return {
            "signals": signals,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(signals)
        }

    async def _ingest_macro(self) -> list[str]:
        """
        Ingest macroeconomic signals.
        Production: FRED / Yield Curve. Currently leveraging 10Y Note, DXY.
        """
        logger.debug("DhatuOracle: Ingesting macro data...")
        results = []
        r1 = await self._ticker_cache.get_or_fetch(
            "macro_TNX",
            lambda: self._fetch_yf_ticker_data("^TNX", "10-Year Treasury Yield"),
            ttl=300,
        )
        r2 = await self._ticker_cache.get_or_fetch(
            "macro_DXY", lambda: self._fetch_yf_ticker_data("DX-Y.NYB", "US Dollar Index"), ttl=300
        )
        results.extend(r1 or [])
        results.extend(r2 or [])
        return results

    async def _ingest_physical(self) -> list[str]:
        """
        Ingest physical world signals.
        Production: NOAA / EIA. Currently leveraging Crude Oil, Gold, Wheat.
        """
        logger.debug("DhatuOracle: Ingesting physical world data...")
        results = []
        for sym, name in [
            ("CL=F", "Crude Oil Futures"),
            ("GC=F", "Gold Futures"),
            ("ZW=F", "Wheat Futures"),
        ]:
            r = await self._ticker_cache.get_or_fetch(
                f"phys_{sym}", lambda s=sym, n=name: self._fetch_yf_ticker_data(s, n), ttl=300
            )
            results.extend(r or [])
        return results

    async def _ingest_corporate(self) -> list[str]:
        """
        Ingest corporate signals with breadth expansion (Samvid v1.0-beta-beta-beta / GAP-41 FIX).
        Check SPY (Cap-Weighted), RSP (Equal-Weighted), and IWM (Small-Cap).
        """
        logger.debug("DhatuOracle: Ingesting corporate breadth data...")
        results = []
        for sym, name in [
            ("SPY", "S&P 500 (Market-Cap)"),
            ("RSP", "S&P 500 (Equal-Weight)"),
            ("IWM", "Russell 2000 (Small-Cap)")
        ]:
            r = await self._ticker_cache.get_or_fetch(
                f"corp_{sym}", lambda s=sym, n=name: self._fetch_yf_ticker_data(s, n), ttl=300
            )
            results.extend(r or [])
        return results

    async def _ingest_tech(self) -> list[str]:
        """
        Ingest technology/cyber signals with sector expansion (GAP-41 FIX).
        Includes QQQ (Growth), SMH (Chips), and IGV (Software).
        """
        logger.debug("DhatuOracle: Ingesting tech/cyber sector data...")
        results = []
        for sym, name in [
            ("QQQ", "NASDAQ 100"),
            ("SMH", "Semiconductors ETF"),
            ("IGV", "Tech-Software ETF")
        ]:
            r = await self._ticker_cache.get_or_fetch(
                f"tech_{sym}", lambda s=sym, n=name: self._fetch_yf_ticker_data(s, n), ttl=300
            )
            results.extend(r or [])
        return results

    async def _ingest_market_mechanics(self) -> list[str]:
        """
        Ingest market mechanics signals.
        Production: SpotGamma. Currently leveraging VIX and VVIX.
        """
        logger.debug("DhatuOracle: Ingesting market mechanics data...")
        results = []
        for sym, name in [("^VIX", "CBOE Volatility Index"), ("^VVIX", "VIX of VIX")]:
            r = await self._ticker_cache.get_or_fetch(
                f"mech_{sym}", lambda s=sym, n=name: self._fetch_yf_ticker_data(s, n), ttl=300
            )
            results.extend(r or [])
        return results

    # ------------------------------------------------------------------
    # Stage 2: Gemini — Causation Graph
    # ------------------------------------------------------------------

    async def _call_ollama(self, prompt: str, system_prompt: str = "") -> str | None:
        """DEPRECATED: Ollama has been removed to preserve RAM and speed (Samvid v1.0-beta-beta-beta)."""
        return None

    async def _rule_based_synthesis(self, signals: list[str]) -> OracleState:
        """
        Deterministic fallback synthesis.
        GAP-80 FIX: Implements Absolute Value Parsing to prevent Semantic Drift.
        """
        logger.info("DhatuOracle: Executing Rule-Based Deterministic Fallback (v1.0-beta-beta Semantic)")

        def extract_val(text: str) -> float | None:
            # Pattern for: Ticker (SYM): -123.45 (change: +1.2%)
            # GAP-80 Fix: Include optional minus sign
            m = re.search(r":\s*(-?[\d\.]+)", text)
            return float(m.group(1)) if m else None

        score = 0
        vix_abs = 0.0

        # 1. ANALYZE ABSOLUTE LEVELS & CHANGES
        for s in signals:
            s_up = s.upper()
            val = extract_val(s)

            # VIX SENSING
            if "VIX" in s_up:
                if val and val > 28.0:
                    score -= 3 # Absolute High Volatility
                    vix_abs = val
                if "+" in s or "UP" in s_up: score -= 1 # Momentum

            # S&P 500 SENSING
            if "S&P 500" in s_up or "SPY" in s_up:
                if "-" in s or "DOWN" in s_up: score -= 2
                if "+" in s or "UP" in s_up: score += 1

            # YIELD / GOLD SENSING (CROSS-ASSET)
            if "YIELD" in s_up and val and val < 3.50: score -= 1 # Bond bid (Flight to quality)
            if "GOLD" in s_up and val and val > 2200: score -= 1 # Safe haven premium

        # 2. INJECT INTELLIGENCE PIPELINE SIGNALS
        macro_bear = any("[MACRO_IMPACT] BEARISH" in s for s in signals)
        macro_bull = any("[MACRO_IMPACT] BULLISH" in s for s in signals)
        flow_bear = any("[INST_FLOW]" in s and "BEARISH" in s for s in signals)
        flow_bull = any("[INST_FLOW]" in s and "BULLISH" in s for s in signals)

        if macro_bear: score -= 3
        if macro_bull: score += 3
        if flow_bear: score -= 2
        if flow_bull: score += 2

        # 3. MAP TO DHATU STATES
        if score <= -6 or vix_abs > 40.0:
            dhatu = "Abhava"  # Cash (Crisis)
        elif score <= -3:
            dhatu = "Chala"   # Volatile (Reduce)
        elif score < 0:
            dhatu = "Kshaya"  # Decay (Hedge)
        elif score >= 5:
            dhatu = "Vriddhi" # Growth (Max)
        elif score >= 2:
            dhatu = "Samyoga" # Conjunction (Aggressive)
        else:
            dhatu = "Sthiti"  # Neutral

        protocol = DHATU_PROTOCOL_MAP.get(dhatu, DHATU_PROTOCOL_MAP["Sthiti"])

        return OracleState(
            dhatu_state=dhatu,
            action_protocol=protocol["action"],
            risk_modifier=float(protocol["risk_modifier"]),
            causation_summary=(
                f"Rule-Based Fallback v1.0-beta-beta: Score {score}. "
                f"VIX Absolute: {vix_abs:.2f}."
            ),
            confidence=0.35,
            source_graph=CausationGraph(dominant_theme="SYSTEM_FALLBACK", macro_bias="NEUTRAL"),
        )

    async def _build_causation_graph(
        self,
        all_signals: list[str],
    ) -> CausationGraph:
        """
        Multi-tier Graph Synthesis:
        Tier 1: Heuristic Engine (Samvid v1.0-beta-beta-beta)
        Tier 2: Global Resonance
        """
        # GAP-88 FIX: Pointing broken LLM-stub to the robust heuristic engine
        return await self._synthesize_oracle_state(all_signals)

    # =========================================================================
    # EFFORT-SCALED MACRO PROCESSOR (Samvid v1.0-beta-beta-beta)
    # =========================================================================

    def _evaluate_effort_needs(self, vix: float, uncertainty: float) -> str:
        """
        Claude-Code Pattern: EFFORT_LEVELS ['low', 'medium', 'high', 'max']
        Scales thinking budget based on market disorder.
        """
        if vix > 33 or uncertainty > 0.7: return "max"
        if vix > 25: return "high"
        if vix > 18: return "medium"
        return "low"

    async def _synthesize_oracle_state(self, signals: list[str]) -> CausationGraph:
        """
        Synthesizes the global macro regime using Adaptive Effort Scaling logic
        ported from Anthropic's Claude-Code codebase.
        """
        logger.info("DhatuOracle: Initiating Adaptive Macro Synthesis...")

        signals_up = [s.upper() for s in signals]
        all_text = " ".join(signals_up)

        # 0. PRELIMINARY VIX SCAN for Effort Scaling
        import re
        vix_m = re.search(r"VIX:\s*([\d\.]+)", all_text)
        vix_val = float(vix_m.group(1)) if vix_m else 20.0

        # Adaptive Effort (Claude Rule #11)
        effort = self._evaluate_effort_needs(vix_val, 0.5)
        logger.info(f"Dhatu_Oracle: Using {effort.upper()} effort for Macro Synthesis.")

        # DEBUG: Log the first 500 chars of the collected text
        logger.info(f"Dhatu_Oracle: RAW SIGNAL TEXT: {all_text[:500]}...")

        # Scaler
        effort_mult = {"low": 1, "medium": 3, "high": 5, "max": 10}[effort]

        # 1. INSTITUTIONAL SENTIMENT MAP (Scaled by Effort)

        # 2. CAUSATION EDGE GENERATION (Scaled Depth)
        edges = []
        macro_score = 0

        # [LOW EFFORT PASS]
        if "YIELD_UP" in all_text:
            macro_score -= 2
            edges.append(CausationEdge("YIELD_UP", "VALUATION_TENSION", "Standard Compression", 0.85))

        # [MEDIUM+ EFFORT PASSES]
        if effort_mult >= 3:
             # Deep Correlation Matrix
             if "NASDAQ_UP" in all_text and "YIELD_UP" in all_text:
                  edges.append(CausationEdge("DIVERGENCE", "BULL_TRAP", "Liquidity Hazard", 0.95))
                  macro_score -= 5

        # [MAX EFFORT PASSES]
        if effort_mult == 10:
             # Recursive Logic: Check for 'Panic-Loop' signals
             if vix_val > 35 and "DISTRIBUTION" in all_text:
                  edges.append(CausationEdge("SYSTEMIC_FAILURE", "LIQUIDITY_CRUNCH", "Sovereign Event Horizontal", 1.0))
                  macro_score -= 20 # Absolute Veto triggering logic

        # --- BULLISH TRIGGERS (GAP-88 RESTORATION) ---
        if "NASDAQ_UP" in all_text and "YIELD_DOWN" in all_text:
             macro_score += 8
             edges.append(CausationEdge("GOLDILOCKS", "EQUITY_EXPANSION", "Monetary Ease Resonance", 0.9))

        if "BTC_UP" in all_text and "NASDAQ_UP" in all_text:
             macro_score += 4
             edges.append(CausationEdge("RISK_ON", "SPECULATIVE_PULSE", "High Beta Alignment", 0.85))

        if "GOLD_DOWN" in all_text and "DXY_DOWN" in all_text:
             macro_score += 3
             edges.append(CausationEdge("DOLLAR_WEAKNESS", "COMMODITY_FLIGHT", "Capital Rotation", 0.75))

        # FINAL BIAS (Standard Algorithm continues)
        logger.info(f"Dhatu_Oracle: Heuristic Final Score: {macro_score} (Edges: {len(edges)})")
        macro_bias = "NEUTRAL"
        if macro_score > 4: macro_bias = "BULLISH"
        elif macro_score < -4: macro_bias = "BEARISH"

        uncertainty = 1.0 - min(0.9, (len(edges) * 0.2))

        return CausationGraph(
            macro_bias=macro_bias,
            dominant_theme="ADAPTIVE_" + effort.upper(),
            edges=edges,
            uncertainty_score=round(float(uncertainty), 3)
        )

    def _parse_graph_json(self, data: dict[str, Any]) -> CausationGraph:
        """Helper to parse raw JSON into CausationGraph object."""
        raw_edges = data.get("edges", [])
        edges: list[CausationEdge] = []
        for e in raw_edges:
            edges.append(
                CausationEdge(
                    source=str(e.get("source", "")),
                    effect=str(e.get("effect", "")),
                    mechanism=str(e.get("mechanism", "")),
                    confidence=float(e.get("confidence", 0.5)),
                )
            )
        return CausationGraph(
            edges=edges,
            dominant_theme=str(data.get("dominant_theme", "NEUTRAL")),
            macro_bias=str(data.get("macro_bias", "NEUTRAL")),
            uncertainty_score=float(data.get("uncertainty_score", 0.5)),
        )

    # ------------------------------------------------------------------
    # Stage 3: Claude — Dhatu State Mapping
    # ------------------------------------------------------------------

    async def _map_to_dhatu_state(
        self, graph: CausationGraph, all_signals: list[str]
    ) -> OracleState:
        """
        Samvid v1.0-beta-beta-beta: Semantic Archetype Resonance.
        Actual reasoning without Ollama via Vector Similarity.
        """
        logger.info("DhatuOracle: Initiating Semantic Resonance Chain...")

        # 1. Prepare Narrative Vector
        narrative = f"Theme: {graph.dominant_theme}. Bias: {graph.macro_bias}. Certainty: {graph.certainty:.1%}. " + ". ".join(all_signals)

        # 2. Define Dhatu Archetype Definitions (The 'Intelligence' library)
        archetypes = {
            "Samyoga": "Strong alignment of catalysts, stable bullish momentum, order in market flow, high confidence.",
            "Viyoga": "Divergence between price and momentum, structural disconnection, mixed signals, uncertainty rising.",
            "Abhava": "Extreme volatility, structural chaos, absence of liquidity, total dissolution of order, panic.",
            "Vriddhi": "Expansion of alpha, accelerating growth, strong institutional buy pressure.",
            "Kshaya": "Decay of momentum, heavy selling pressure, weakening structural support, breakdown.",
            "Sthira": "Equilibrium, range-bound stability, neutral bias, balanced market forces.",
            "Chala": "Agitated movement, micro-fluctuations, high frequency noise, lack of clear direction."
        }

        try:
            from embedding_engine import SharedEmbeddingEngine
            engine = SharedEmbeddingEngine()

            # Embed both the narrative and the archetypes
            narrative_vec = engine.embed([narrative])[0]
            archetype_keys = list(archetypes.keys())
            archetype_vecs = engine.embed(list(archetypes.values()))

            # 3. COGNITIVE CALCULATION: Cosine Similarity Resonance
            import math
            def cosine_sim(v1, v2):
                dot = sum(a*b for a, b in zip(v1, v2, strict=False))
                mag1 = math.sqrt(sum(a*a for a in v1))
                mag2 = math.sqrt(sum(a*a for a in v2))
                return dot / (mag1 * mag2 + 1e-10)

            scores = [cosine_sim(narrative_vec, av) for av in archetype_vecs]

            # Find the best match (The 'Reasoning' Result)
            top_idx = scores.index(max(scores))
            state_name = archetype_keys[top_idx]
            confidence = scores[top_idx]

            reasoning = f"Semantic resonance detected match with {state_name} ({confidence:.1%} similarity). "
            reasoning += f"Primary themes: {graph.dominant_theme} and {graph.macro_bias}. Certainty: {graph.certainty:.1%}."

        except Exception as e:
            logger.error(f"DhatuOracle: Semantic reasoning failed: {e}. Falling back to Rule-Engine.")
            # Deterministic Fallback if Embedding Engine fails
            state_name = "Sthira"
            if graph.macro_bias == "BULLISH":
                state_name = "Samyoga"
            elif graph.macro_bias == "BEARISH":
                state_name = "Kshaya"
            confidence = 0.5
            reasoning = "Rule-based fallback active."

        # Samvid v1.0-beta-beta-beta: Extract protocol details from map
        protocol = DHATU_PROTOCOL_MAP.get(state_name, DHATU_PROTOCOL_MAP["Sthiti"])

        return OracleState(
            dhatu_state=state_name,
            action_protocol=protocol["action"],
            risk_modifier=protocol["risk_modifier"],
            causation_summary=reasoning,
            confidence=round(confidence, 4),
            source_graph=graph
        )

    def _parse_state_json(self, data: dict[str, Any], graph: CausationGraph) -> OracleState:
        """Deprecated: Replaced by deterministic state mapping."""
        return OracleState(dhatu_state="Sthiti", reasoning="Deprecated")

    # ------------------------------------------------------------------
    # Full Synthesis Cycle
    # ------------------------------------------------------------------

    async def _full_synthesis_cycle(self) -> OracleState | None:
        """Run all layers with tiered fallback and return the final OracleState."""
        # Layer 1: Ingestion
        results = await asyncio.gather(
            self._ingest_geopolitical(),
            self._ingest_macro(),
            self._ingest_physical(),
            self._ingest_corporate(),
            self._ingest_tech(),
            self._ingest_market_mechanics(),
            return_exceptions=True,
        )

        all_signals: list[str] = []
        for r in results:
            if isinstance(r, list):
                all_signals.extend(r)

        # Samvid v1.0-beta-beta-beta: Inject Live Intelligence Buffers
        if self._news_buffer:
            all_signals.extend(self._news_buffer)
            self._news_buffer = [] # Clear

        if self._macro_buffer:
            all_signals.extend(self._macro_buffer)
            self._macro_buffer = []

        if self._flow_buffer:
            all_signals.extend(self._flow_buffer)
            self._flow_buffer = []

        logger.info(f"DhatuOracle: {len(all_signals)} total signals (including pipeline intel) collected for synthesis.")

        # Tiered Synthesis
        # Layer 2: Causation Graph
        graph = await self._build_causation_graph(all_signals)

        # Layer 3: Dhatu State Mapping
        state = await self._map_to_dhatu_state(graph, all_signals)

        # --- BAYESIAN CONFIDENCE BLENDING (GAP-54) ---
        if state is not None:
             try:
                 # Extract most recent price/vix data from internal cache or synthesis
                 # We use SPY as the proxy for global regime sentiment
                 vix = 15.0
                 prices = np.array([])
                 volumes = np.array([])

                 # Attempt to find prices in graph or news context
                 if self._ticker_cache:
                     spy_data = await self._ticker_cache.get("SPY")
                     if spy_data and isinstance(spy_data, dict):
                         prices = np.array(spy_data.get("prices", []))
                         volumes = np.array(spy_data.get("volumes", []))

                 if len(prices) >= 10:
                     bayes_state = self._bayesian_oracle.update(prices, volumes, vix)
                     original_conf = state.confidence
                     blended_conf = (0.6 * bayes_state.confidence) + (0.4 * original_conf)
                     state.confidence = round(float(blended_conf), 4)
                     logger.info(f"DhatuOracle: Bayesian confidence blended. {state.dhatu_state} (New Conf: {state.confidence:.1%})")
             except Exception as be:
                 logger.debug(f"DhatuOracle: Bayesian blending skipped: {be}")

        return state
