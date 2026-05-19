"""
tools/fix_bugs.py
Sovereign Bug Fix Script
Fixes all confirmed bugs found by deep_bug_check.py
"""

import logging
from pathlib import Path

SRC = Path("src")


def fix_file(path, replacements, label):
    code = path.read_text(encoding="utf-8", errors="replace")
    original = code
    for old, new in replacements:
        code = code.replace(old, new)
    if code != original:
        path.write_text(code, encoding="utf-8")
        print(f"  FIXED: {label}")
        return True
    else:
        print(f"  OK (no change needed): {label}")
        return False


# ── 1. session_restorer.py: duplicate unreachable return ─────────────────────
fix_file(
    SRC / "session_restorer.py",
    [
        (
            '            logger.error(f"Reconciler: Recovery Loop Failed: {e}")\n            return []\n            return []',
            '            logger.error(f"Reconciler: Recovery Loop Failed: {e}")\n            return []',
        )
    ],
    "session_restorer.py: removed unreachable duplicate return []",
)

# ── 2. brain.py: silent except:pass in state restore → log at DEBUG ───────────
brain_path = SRC / "brain.py"
fix_file(
    brain_path,
    [
        # Position restore: swallow ValueError from bad field data
        (
            "                        except Exception:\n                            pass\n\n                self.ibkr_drawdown.peak_equity",
            '                        except Exception as _pos_err:\n                            logger.debug(f"Brain: Skipping malformed position state entry: {_pos_err}")\n\n                self.ibkr_drawdown.peak_equity',
        ),
        # loss_tracker datetime parse: swallow bad ISO string
        (
            '                        except Exception:\n                            pass\n\n                logger.info(\n                    f"MindBrain: Legacy state thawed',
            '                        except Exception as _dt_err:\n                            logger.debug(f"Brain: Skipping bad last_loss_time format: {_dt_err}")\n\n                logger.info(\n                    f"MindBrain: Legacy state thawed',
        ),
        # session_restorer call: swallow startup DB error
        (
            "        except Exception:\n            pass\n\n    async def quant_gate",
            '        except Exception as _sr_err:\n            logger.debug(f"Brain: Non-critical session restore error (continuing): {_sr_err}")\n\n    async def quant_gate',
        ),
    ],
    "brain.py: converted 3 silent except:pass to logged DEBUG",
)

# ── 3. data_pipeline.py: yfinance patch silent except → debug log ────────────
fix_file(
    SRC / "data_pipeline.py",
    [
        (
            "except Exception:\n    pass\nimport yfinance as yf",
            "except Exception as _yf_patch_err:\n    pass  # yfinance version mismatch — patch not applied (non-critical)\nimport yfinance as yf",
        )
    ],
    "data_pipeline.py: yfinance patch except annotated",
)

# ── 4. intelligence_bus.py: relay cleanup silent except → debug log ───────────
fix_file(
    SRC / "intelligence_bus.py",
    [
        (
            "        except Exception:\n            pass\n        finally:\n            if q in self._relay_queues:\n                self._relay_queues.remove(q)",
            '        except Exception as _relay_err:\n            logger.debug(f"BUS: Relay loop ended with error (non-critical): {_relay_err}")\n        finally:\n            if q in self._relay_queues:\n                self._relay_queues.remove(q)',
        )
    ],
    "intelligence_bus.py: relay cleanup exception now logged at DEBUG",
)

# ── 5. mind_ultrathink.py: 5 bare except: → except Exception: ────────────────
fix_file(
    SRC / "mind_ultrathink.py",
    [
        # weights load
        (
            "            except:\n                pass\n\n        # Initial Global Knowledge",
            "            except Exception:\n                pass\n\n        # Initial Global Knowledge",
        ),
        # wisdom text load
        (
            "        except:\n            pass\n        return wisdom_text",
            "        except Exception:\n            pass\n        return wisdom_text",
        ),
        # memory load
        (
            "            except:\n                pass\n\n    def _save_memory",
            "            except Exception:\n                pass\n\n    def _save_memory",
        ),
        # save memory
        (
            "        except:\n            pass\n\n    async def start",
            "        except Exception:\n            pass\n\n    async def start",
        ),
        # JSON parse
        (
            "            except:\n                pass\n            return {}",
            "            except Exception:\n                pass\n            return {}",
        ),
    ],
    "mind_ultrathink.py: 5 bare except: upgraded to except Exception:",
)

# ── 6. swarm_predictor.py: silent weight storage → debug log ─────────────────
fix_file(
    SRC / "swarm_predictor.py",
    [
        (
            "            except Exception:\n                pass\n\n        return consensus",
            '            except Exception as _sw_err:\n                logger.debug(f"Swarm: Non-critical advisor weight error: {_sw_err}")\n\n        return consensus',
        )
    ],
    "swarm_predictor.py: silent advisor weight error now logged at DEBUG",
)

# ── 7. dhatu_oracle.py: JSON parse silent → debug log ────────────────────────
fix_file(
    SRC / "dhatu_oracle.py",
    [
        (
            "        except Exception:\n            pass\n        return results",
            '        except Exception as _dh_err:\n            logger.debug(f"DhatuOracle: JSON parse error in stream (non-critical): {_dh_err}")\n        return results',
        )
    ],
    "dhatu_oracle.py: JSON parse exception now logged at DEBUG",
)

# ── 8. ibkr_streamer.py: 4 silent except → debug log ────────────────────────
ibkr_path = SRC / "ibkr_streamer.py"
fix_file(
    ibkr_path,
    [
        # QuestDB write error
        (
            "                except Exception:\n                    pass\n\n            if self.bus is not None",
            '                except Exception as _qdb_err:\n                    logger.debug(f"IBKRStreamer: QuestDB write skipped: {_qdb_err}")\n\n            if self.bus is not None',
        ),
        # Event disconnect (deduplication guard)
        (
            "                try:\n                    self.ib.pendingTickersEvent.disconnect(self.on_tick)\n                except Exception:\n                    pass\n                self.ib.pendingTickersEvent.connect",
            "                try:\n                    self.ib.pendingTickersEvent.disconnect(self.on_tick)\n                except Exception:\n                    pass  # Expected if not previously connected\n                self.ib.pendingTickersEvent.connect",
        ),
        # Cleanup disconnect
        (
            "                try:\n                    self.ib.pendingTickersEvent.disconnect(self.on_tick)\n                except Exception:\n                    pass\n                if self.ib.isConnected",
            "                try:\n                    self.ib.pendingTickersEvent.disconnect(self.on_tick)\n                except Exception:\n                    pass  # Expected if not connected\n                if self.ib.isConnected",
        ),
        # ib.disconnect
        (
            "                    except Exception:\n                        pass\n\n    async def stop",
            '                    except Exception as _disc_err:\n                        logger.debug(f"IBKRStreamer: Non-critical disconnect error: {_disc_err}")\n\n    async def stop',
        ),
    ],
    "ibkr_streamer.py: 4 silent excepts annotated with debug comments/logs",
)

# ── 9. session_restorer.py: silent ghost check → debug log ───────────────────
fix_file(
    SRC / "session_restorer.py",
    [
        (
            '                    except Exception:\n                        pass\n\n                    logger.info(\n                        f"👻 Reconciler: GHOST DETECTED',
            '                    except Exception as _ghost_err:\n                        logger.debug(f"Reconciler: Ghost age check error (non-critical): {_ghost_err}")\n\n                    logger.info(\n                        f"👻 Reconciler: GHOST DETECTED',
        )
    ],
    "session_restorer.py: ghost check silent except now logged at DEBUG",
)

print("\nAll bug fixes applied.")
