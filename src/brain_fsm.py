"""
src/brain_fsm.py
Brain finite-state machine enum — extracted from brain.py so mixins can import it.

TradingState drives the main _run_loop dispatch in TradingBrain.
"""
from __future__ import annotations

from enum import Enum


class TradingState(Enum):
    STANDBY = 1
    SCANNING = 2
    ANALYZING = 3
    POSITIONED = 4
    EXIT = 5
