"""Quick sanity check: simulate sizing for GS and MA with the fix applied."""
import sys
sys.path.insert(0, '.')
from src.agent_c_ibkr import PositionSizingChain, PortfolioGuard # type: ignore

sizer = PositionSizingChain()
guard = PortfolioGuard()

account = 10000.0

tests = [
    {"sym": "GS", "win_prob": 0.83, "rr": 3.6, "entry": 858.0,  "stop": 840.0},
    {"sym": "MA", "win_prob": 0.83, "rr": 6.3, "entry": 488.0,  "stop": 475.0},
    {"sym": "SPY","win_prob": 0.60, "rr": 2.0, "entry": 550.0,  "stop": 546.0},
]

print(f"Account: ${account:,.0f}  Max Investable (80%): ${account*0.8:,.0f}")
print(f"Cash Reserve: 20% = ${account*0.2:,.0f}\n")

for t in tests:
    result = sizer.calculate(
        win_prob=t["win_prob"],
        rr_ratio=t["rr"],
        balance=account,
        account_value=account,
        entry_price=t["entry"],
        stop_price=t["stop"],
        instrument=t["sym"],
        regime="CHOPPY",
        regime_modifier=1.0,
        drawdown_modifier=1.0,
        loss_modifier=1.0,
    )
    shares = result["step8_shares"]
    pos_val = result["position_value"]
    guard_ok = guard.enforce_cash_reserve(account, pos_val)
    print(f"{t['sym']:6s}: shares={shares}  pos_value=${pos_val:,.0f}  guard={'✅ OK' if guard_ok else '❌ BLOCKED'}")
