import asyncio
import os
import sys
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from brain import TradingBrain
from system_types import Position
from exit_intelligence import ExitAction, ExitDecision
from datetime import datetime

async def test_lifecycle():
    logging.basicConfig(level=logging.INFO)
    brain = TradingBrain(mode="paper")
    print("\n[TEST] 1. Initialized TradingBrain in PAPER mode.")
    
    # Fake Pos
    pos = Position(
        symbol="MOCK",
        qty=100.0,
        entry_price=100.0,
        entry_time=datetime.now(),
        pattern="BULL_FLAG",
        initial_belief=0.5,
        current_belief=0.5,
        initial_stop=98.0, # risk $2
        stop_loss=98.0,
        take_profit=110.0,
        trade_id="TEST-123",
        account_type="ibkr",
        catalyst_score=85.0,
        regime_at_entry="TRENDING",
        commission_cost=2.0,  # $2 entry
        slippage_cost=0.5,    # fake slip
    )
    # Insert DB record simulating coordinator
    if brain.db_conn:
        cursor = brain.db_conn.cursor()
        cursor.execute(
            "INSERT INTO trades (timestamp, instrument, direction, pattern, regime, entry_price, stop_price, target_price, shares, outcome, broker, commission, slippage) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), "MOCK", "LONG", "BULL_FLAG", "TRENDING", 100.0, 98.0, 110.0, 100.0, "OPEN", "ibkr", 2.0, 0.5)
        )
        brain.db_conn.commit()

    brain.positions.append(pos)
    print("\n[TEST] 2. Position created. Qty:", pos.qty, "Entry:", pos.entry_price)

    # Simulate market hitting 103 (+1.5R) -> Partial 50%
    current_price = 103.0 
    pos.mfe = 1.5
    
    pos_dict = {
        "symbol": pos.symbol,
        "side": "long",
        "quantity": pos.qty,
        "entry_price": pos.entry_price,
        "stop_loss": pos.stop_loss,
        "initial_stop": pos.initial_stop,
        "bayesian_belief": pos.current_belief,
        "initial_belief": pos.initial_belief,
        "mfe_r": pos.mfe,
        "runner_active": getattr(pos, "runner_active", False)
    }
    market_dict = {
        "price": current_price,
        "vix": 15.0,
        "vix_baseline": 15.0,
    }
    account_dict = {
        "equity": 5000.0,
        "daily_pnl": 0.0,
    }
    
    decision = brain.exit_engine.evaluate(pos_dict, market_dict, account_dict)
    print(f"\n[TEST] 3. Decision at {current_price}: {decision}")
    
    if decision.action == ExitAction.PARTIAL:
        pos.runner_active = True
        pos.shares_remaining = 0.5
        print("\n[TEST] 4. Triggering PARTIAL Exit processing...")
        await brain._process_exit(pos, "PARTIAL", current_price)
        print(" -> Remaining Qty inside brain:", pos.qty)
        print(" -> Accrued Net PnL:", pos.net_pnl)
        
    # Simulate market crashing to trailing stop (which would be at 102.0 after TIGHTEN)
    current_price = 101.5
    decision2 = brain.exit_engine.evaluate({**pos_dict, "mfe_r": 1.6, "quantity": pos.qty, "runner_active": True}, market_dict, account_dict)
    # the second evaluation should yield HOLD or EXIT depending on stop loss. 
    # Let's forcefully call trailing stop EXIT.
    print(f"\n[TEST] 5. Force closing remainder at {current_price}...")
    await brain._process_exit(pos, "EXIT_P2", current_price)
    
    print("\n[TEST] 6. Final state:")
    print(" -> Final Net PnL:", pos.net_pnl)
    print(" -> Final Qty left in positions:", len(brain.positions))
    
    # Read DB to ensure it was logged
    if brain.db_conn:
       cursor = brain.db_conn.cursor()
       cursor.execute("SELECT instrument, outcome, net_pnl, commission FROM trades WHERE instrument='MOCK' ORDER BY id DESC LIMIT 1")
       row = cursor.fetchone()
       print("\n[TEST] 7. DB Read:", row)

if __name__ == "__main__":
    asyncio.run(test_lifecycle())
