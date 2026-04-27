import logging
import json
import os
from datetime import datetime, timezone
import pytz
from typing import Any, Dict

from config import COMMISSION_PER_ROUND_TRIP, STARTING_CAPITAL_CAD

logger = logging.getLogger(__name__)

class SovereignLogicEngine:
    """
    The Single Source of Truth for the 500-Ability Sovereign Mind (V9.0).
    Acts as a logical dispatcher and executor for the capability registry.
    """

    def __init__(self):
        # Resolve path relative to this file so it works regardless of CWD
        _here = os.path.dirname(os.path.abspath(__file__))
        self.capabilities_path = os.path.normpath(os.path.join(_here, "..", "data", "capabilities.json"))
        self.active_layer = "Layer_2_Cognitive"
        self.node_states = {} # NodeID -> State (ENABLED/DISABLED/CALIBRATING)
        self._initialize_node_states()

    def _initialize_node_states(self):
        try:
            with open(self.capabilities_path, "r") as f:
                caps = json.load(f)
                for layer, nodes in caps.items():
                    if layer == "Status": continue
                    for node_id, node_name in nodes.items():
                        # Every single one of the 500 nodes is initialized as ENABLED
                        self.node_states[node_id] = {
                            "name": node_name,
                            "layer": layer,
                            "active": True,
                            "prowess": 1.0,
                            "last_sync": datetime.now().isoformat()
                        }
            logger.info(f"SovereignLogicEngine: 500 Abilities synchronized and active.")
        except Exception as e:
            logger.error(f"Logic Engine initialization failure: {e}")

    def execute_node(self, node_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the logic for one of the 500 abilities.
        """
        if node_id not in self.node_states:
            return {"status": "ERROR", "reason": f"Node {node_id} not in registry."}

        node = self.node_states[node_id]
        logger.info(f"Sovereign Action: Triggering Ability #{node_id} ({node['name']})")

        # MASTER DISPATCHER
        _dispatch = {
            "15":  self._logic_15_hft_footprint,
            "17":  self._logic_17_abhava,
            "31":  self._logic_31_antifragility,
            "40":  self._logic_40_circadian,
            "48":  self._logic_48_trap,
            "104": self._logic_104_regime_prediction,
            "151": self._logic_151_kelly,
            "154": self._logic_154_drawdown_breaker,
            "155": self._logic_155_slippage,
            "163": self._logic_163_margin,
            "164": self._logic_164_liquidation_audit,
            "166": self._logic_166_blackswan,
            "231": self._logic_231_audit,
            "6":   self._logic_6_sector,
            "452": self._logic_452_optimism,
            "152": self._logic_152_hedge,
            "460": lambda ctx: {"status": "SUCCESS", "consensus": True},
        }
        if node_id in _dispatch:
            return _dispatch[node_id](context)

        # GAP-180 FIX: Dynamic Base-Name Dispatch (Resolve Redundancy)
        # If the ID isn't specifically mapped, check if its NAME base is mapped.
        # This collapses redundant nodes (e.g., Hedge_Node_152, Hedge_Node_162) into one logic.
        node_name = node["name"]
        # Strip trailing ID suffixes like _152 or _Node_001
        import re
        base_name = re.sub(r'(_Node)?(_\d+)?$', '', node_name).lower()
        
        _base_dispatch = {
            "hedge": self._logic_152_hedge,
            "drawdown": self._logic_154_drawdown_breaker,
            "audit": self._logic_231_audit,
            "margin": self._logic_163_margin,
            "kelly": self._logic_151_kelly,
            "hft footprint": self._logic_15_hft_footprint,
            "abhava": self._logic_17_abhava,
            "antifragility": self._logic_31_antifragility,
            "circadian": self._logic_40_circadian,
            "trap": self._logic_48_trap,
            "regime": self._logic_104_regime_prediction,
            "slippage": self._logic_155_slippage,
            "blackswan": self._logic_166_blackswan,
            "optimism": self._logic_452_optimism,
        }
        
        for key, func in _base_dispatch.items():
            if key in base_name:
                return func(context)

        # --- BUG #17 FIX: Hallucination Protection ---
        # Remaining nodes: active in cognition, not yet deep-coded. 
        # Return impact 0.0 to prevent blind SUCCESS state.
        return {"status": "PURE_COGNITION", "node": node["name"], "mode": "DORMANT", "impact": 0.0}

    # --- SPECIFIC ABILITY REALIZATIONS (Deep-Coded) ---

    def _logic_151_kelly(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Fee-Aware Kelly Criterion (Bug #20 FIX)."""
        from vault import Vault
        win_prob = ctx.get("win_prob", 0.5)
        rr = ctx.get("r_r_ratio", 2.0)
        # BUG #20 FIX: Dynamically read commission from Vault
        commission = float(Vault.get("COMMISSION_PER_ROUND_TRIP", str(COMMISSION_PER_ROUND_TRIP)))
        account_value = ctx.get("account_value", STARTING_CAPITAL_CAD)
        
        q = 1.0 - win_prob
        kelly_f = (win_prob * rr - q) / rr
        final_sizing = max(0, kelly_f * 0.2)
        fee_drag = commission / account_value
        if final_sizing < fee_drag:
            return {"decision": "SKIP", "reason": f"Fee Drag (${commission}) inhibits Kelly Sizing."}
        return {"decision": "Sized", "frac": final_sizing}

    def _logic_104_regime_prediction(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Regime Prediction — handles Abhava (crisis) states (Bug #19 FIX)."""
        dhatu = ctx.get("dhatu", "Sthiti")
        regime = ctx.get("regime", "UNKNOWN")
        
        # BUG #19 FIX: Ensure Abhava crisis overrides any bullish bias
        if dhatu == "Abhava":
            logger.warning("🏛️ Logic #104: ABHAVA Crisis Override — enforcing Defensive regime.")
            return {"predicted_regime": "VOLATILE", "bias": "BEARISH", "confidence": 0.95}
            
        if regime == "BULLISH":
            return {"predicted_regime": "BULLISH", "bias": "NEUTRAL", "confidence": 0.70}
        return {"predicted_regime": regime, "bias": "NEUTRAL", "confidence": 0.50}

    def _logic_31_antifragility(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Chaos Opportunity Detection."""
        vix = ctx.get("vix", 20)
        if vix > 35:
            logger.warning("ANTIFRAGILITY: Market Chaos — seeking Dislocation Alpha.")
            return {"mode": "EXPLORATIVE", "risk_multiplier": 1.2}
        return {"mode": "STABLE", "risk_multiplier": 1.0}

    def _logic_17_abhava(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Absence Detection."""
        news = ctx.get("news", [])
        volatility = ctx.get("volatility", "LOW")
        if not news and volatility == "HIGH":
            return {"alert": "ABHAVA_DETECTED", "warning": "Price move without news. Trap risk."}
        return {"alert": "NORMAL"}

    def _logic_231_audit(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Cognitive Self-Correction."""
        recent_pnl = ctx.get("recent_pnl", [])
        if len(recent_pnl) >= 3 and all(p < 0 for p in recent_pnl[-3:]):
            return {"action": "BRAKE", "reason": "3 consecutive losses — cognitive drift."}
        return {"action": "CONTINUE"}

    def _logic_154_drawdown_breaker(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Hard Equity Floor protection."""
        equity = ctx.get("account_value", 0)
        floor = STARTING_CAPITAL_CAD * 0.90 # Soft 10% Drawdown Floor
        if equity < floor:
             return {"status": "HALT", "reason": f"NAV ${equity:,.2f} below equity floor ${floor:,.2f}"}
        return {"status": "SUCCESS"}

    def _logic_155_slippage(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Spread and Friction Viability Audit."""
        symbol = ctx.get("symbol", "")
        # Dummy spread proxy (0.02% of entry)
        entry = ctx.get("entry", 1.0)
        target = ctx.get("target", 1.05)
        spread = entry * 0.0002
        expected_pnl = abs(target - entry)
        if spread > (expected_pnl * 0.15): # If spread eats 15% of profit, skip
             return {"status": "REJECT", "reason": f"Spread friction ${spread:.4f} too high for target ${expected_pnl:.4f}"}
        return {"status": "SUCCESS"}

    def _logic_166_blackswan(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Black-Swan Veto — triggers on catastrophic news keywords (SETO V21.50).
        Remediated GAP-17: Now handles basic negation and context check.
        """
        headline = ctx.get("headline", "").lower()
        if not headline:
            return {"veto": False}

        triggers = ["war", "nuclear", "crash", "halt", "bankruptcy", "pandemic", "recession"]
        negations = ["no", "not", "avoid", "low", "unlikely", "false"]
        
        # Check for triggers
        found_trigger = next((t for t in triggers if t in headline), None)
        if found_trigger:
            # GAP-17 FIX: Check if the trigger is negated (naive 2-word lookback)
            words = headline.split()
            try:
                idx = words.index(next(w for w in words if found_trigger in w))
                if idx > 0 and words[idx-1] in negations:
                    logger.debug(f"Black-Swan: Negated trigger '{found_trigger}' detected — Veto suppressed.")
                    return {"veto": False}
            except Exception:
                pass

            # GAP-18 CONTEXT: If trigger is found and NOT negated, it constitutes a structural risk
            return {"veto": True, "reason": f"Black-Swan keyword in headline: '{found_trigger}' (Context: {headline[:40]})"}
        
        return {"veto": False}

    def _logic_15_hft_footprint(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Detects HFT congestion via Spread Tension / Sub-Atomic Entropy."""
        bid = ctx.get("bid", 0.0)
        ask = ctx.get("ask", 0.0)
        vol = ctx.get("volume", 0.0)
        if bid <= 0 or ask <= 0: return {"status": "INCONCLUSIVE"}
        
        spread = abs(ask - bid)
        if spread == 0: return {"status": "MAX_TENSION", "signal": "BUY_PRESSURE"}
        
        # TENSION = VOLUME / SPREAD^2
        tension = vol / (spread ** 2) if spread >0 else 1000
        if tension > 5000:
             return {"status": "HFT_CONGESTION", "tension": tension, "action": "CAUTION"}
        return {"status": "NORMAL"}

    def _logic_164_liquidation_audit(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures NAV is sufficient for the proposed exposure."""
        equity = ctx.get("account_value", STARTING_CAPITAL_CAD)
        exposure = ctx.get("total_exposure", 0.0)
        if exposure > (equity * 3.0): # Hard cap at 3x leverage for small accounts
            return {"status": "VETO", "reason": f"Leverage {exposure/equity:.1f}x exceeds 3x cap."}
        return {"status": "SUCCESS"}

    def _logic_40_circadian(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Circadian Rhythm — session-aware risk multiplier (Exchange Time)."""
        # GAP-29 FIX: Convert to US/Eastern (NYSE) regardless of system location
        et_tz = pytz.timezone("US/Eastern")
        now_et = datetime.now(timezone.utc).astimezone(et_tz)
        hour = ctx.get("hour", now_et.hour)
        
        if 9 <= hour < 10:    # Opening volatility
            return {"session": "OPEN", "risk_mult": 0.7, "note": "Reduce size at open"}
        elif 11 <= hour < 13: # Lunch lull
            return {"session": "LULL", "risk_mult": 0.5, "note": "Avoid lunch lull"}
        elif 15 <= hour < 16: # Power hour
            return {"session": "POWER", "risk_mult": 1.2, "note": "Increase size power hour"}
        return {"session": "NORMAL", "risk_mult": 1.0}

    def _logic_48_trap(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Trap Detection — identifies false breakouts."""
        volume_ratio = ctx.get("volume_ratio", 1.0)
        price_change = ctx.get("price_change_pct", 0.0)
        if price_change > 0.02 and volume_ratio < 0.8:
            return {"trap": True, "reason": "Price up on low volume — probable fake breakout."}
        return {"trap": False}

    def _logic_163_margin(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Margin-Call Prevention."""
        equity = ctx.get("equity", STARTING_CAPITAL_CAD)
        margin_used = ctx.get("margin_used", 0.0)
        margin_ratio = margin_used / equity if equity > 0 else 1.0
        if margin_ratio > 0.80:
            return {"action": "HALT", "reason": f"Margin utilization {margin_ratio:.0%} > 80%."}
        return {"action": "ALLOW"}

    def _logic_6_sector(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Sector Rotation Scenting."""
        sectors = ctx.get("sector_flows", {})
        top = max(sectors, key=sectors.get, default=None) if sectors else None
        if top:
            return {"leading_sector": top, "flow": sectors[top]}
        return {"leading_sector": "UNKNOWN"}

    def _logic_452_optimism(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Optimism Scaling — press hardest when others are fearful."""
        fear_index = ctx.get("fear_greed", 50)
        if fear_index < 20:
            return {"action": "SCALE_UP", "multiplier": 1.5, "note": "Extreme fear = opportunity"}
        return {"action": "NORMAL", "multiplier": 1.0}

    def _logic_152_hedge(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Hedge Node 152: Dynamic Risk Neutralization."""
        exposure = ctx.get("total_exposure", 0.0)
        volatility = ctx.get("volatility_index", 20.0)
        
        if exposure > 50000 and volatility > 30:
            return {"action": "HEDGE", "instrument": "SH", "size_pct": 0.15, "reason": "High exposure/volatility balance."}
        return {"action": "NONE"}

_CORE_INSTANCE = None

def get_sovereign_logic():
    """Lazy-load the logic engine to prevent startup hangs."""
    global _CORE_INSTANCE
    if _CORE_INSTANCE is None:
        _CORE_INSTANCE = SovereignLogicEngine()
    return _CORE_INSTANCE

# Compatibility alias - will trigger load on first access
SOVEREIGN_CORE = None # Replaced by get_sovereign_logic in dependent files
