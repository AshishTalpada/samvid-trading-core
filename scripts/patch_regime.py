"""One-shot patch script: add timing logs to _detect_regime in brain_data.py."""
import pathlib

target = pathlib.Path("src/brain_data.py")
content = target.read_text(encoding="utf-8")

OLD = (
    "    async def _detect_regime(self) -> str:\n"
    '        """Use Agent D\'s regime classifier with REAL market data from database."""\n'
    "        try:\n"
    "            vix = await self._get_vix()\n"
    "\n"
    "            momentum = 0.0\n"
    "            spy_above_200ma = True\n"
    "            if len(self.spy_buffer) >= 20:\n"
    "                l_spy = list(self.spy_buffer)\n"
    "                momentum = (l_spy[-1] - l_spy[-20]) / l_spy[-20] if l_spy[-20] != 0 else 0\n"
    "                if len(l_spy) >= 200:\n"
    "                    sma_200 = sum(l_spy) / 200\n"
    "                    spy_above_200ma = l_spy[-1] > sma_200\n"
    "            elif self.db_conn:\n"
    "                try:\n"
    "                    spy_df = await asyncio.to_thread(\n"
    "                        pd.read_sql_query,\n"
    '                        "SELECT close FROM ohlcv WHERE symbol=\'SPY\' AND timeframe=\'1d\' "\n'
    '                        "ORDER BY timestamp DESC LIMIT 250",\n'
    "                        self.db_conn,\n"
    "                    )\n"
    "                    if not spy_df.empty:\n"
    '                        closes = spy_df["close"].iloc[::-1].tolist()\n'
    "                        if len(closes) >= 20:\n"
    "                            momentum = (\n"
    "                                (closes[-1] - closes[-20]) / closes[-20]\n"
    "                                if closes[-20] != 0\n"
    "                                else 0\n"
    "                            )\n"
    "                        if len(closes) >= 200:\n"
    "                            sma_200 = sum(closes[-200:]) / 200\n"
    "                            spy_above_200ma = closes[-1] > sma_200\n"
    "                            logger.debug(\n"
    '                                "True Daily SMA 200: %.2f (Price: %.2f)", sma_200, closes[-1]\n'
    "                            )\n"
    "                except Exception as e:\n"
    '                    logger.debug("Regime data fallback (1d): %s", e)\n'
    "\n"
    "            breadth = 0.55\n"
    "            if self.db_conn:\n"
    "\n"
    "                def _sync_breadth() -> float:\n"
    "                    try:\n"
    "                        total = 0\n"
    "                        positive = 0\n"
    "                        major_indices = [\n"
    '                            "SPY", "QQQ", "IWM", "DIA", "XLK",\n'
    '                            "NVDA", "MSFT", "AAPL", "TSLA", "META",\n'
    "                        ]\n"
    "                        for sym in major_indices:\n"
    "                            if sym in self.last_tick_prices:\n"
    "                                total += 1\n"
    "                                positive += 1\n"
    "                            else:\n"
    "                                row = pd.read_sql_query(\n"
    '                                    "SELECT close FROM ohlcv WHERE symbol=? "\n'
    '                                    "ORDER BY timestamp DESC LIMIT 2",\n'
    "                                    self.db_conn,\n"
    "                                    params=(sym,),\n"
    "                                )\n"
    "                                if not row.empty and len(row) >= 2:\n"
    "                                    total += 1\n"
    '                                    if row["close"].iloc[0] > row["close"].iloc[1]:\n'
    "                                        positive += 1\n"
    "                        return positive / total if total > 0 else 0.55\n"
    "                    except Exception:\n"
    "                        return 0.55\n"
    "\n"
    "                breadth = await asyncio.to_thread(_sync_breadth)\n"
    "\n"
    "            regime = self.regime_classifier.classify(\n"
    "                vix=vix,\n"
    "                spy_above_200ma=spy_above_200ma,\n"
    "                breadth=breadth,\n"
    "                momentum=momentum,\n"
    "            )\n"
    "            logger.info(\n"
    '                "Regime: %s (VIX=%.1f, Mom=%.4f, Breadth=%.2f, SPY>200MA=%s)",\n'
    "                regime, vix, momentum, breadth, spy_above_200ma,\n"
    "            )\n"
    "            # Persist for state capsule\n"
    "            self.session_restorer.save_cognitive_capsule(\n"
    "                {\n"
    '                    "regime": regime,\n'
    '                    "conviction_state": self.conviction_state,\n'
    '                    "session_pnl": self.session_pnl,\n'
    '                    "session_stats": self.session_stats,\n'
    '                    "timestamp": time.time_ns(),\n'
    "                }\n"
    "            )\n"
    "            return regime\n"
    "        except Exception:\n"
    '            return "CHOPPY"'
)

NEW = (
    "    async def _detect_regime(self) -> str:\n"
    '        """Use Agent D\'s regime classifier with REAL market data from database."""\n'
    "        _t0 = time.perf_counter()\n"
    "        try:\n"
    "            vix = await self._get_vix()\n"
    "            logger.debug(\"Regime step 'vix_fetch' took %.2fs\", time.perf_counter() - _t0)\n"
    "\n"
    "            momentum = 0.0\n"
    "            spy_above_200ma = True\n"
    "            if len(self.spy_buffer) >= 20:\n"
    "                l_spy = list(self.spy_buffer)\n"
    "                momentum = (l_spy[-1] - l_spy[-20]) / l_spy[-20] if l_spy[-20] != 0 else 0\n"
    "                if len(l_spy) >= 200:\n"
    "                    sma_200 = sum(l_spy) / 200\n"
    "                    spy_above_200ma = l_spy[-1] > sma_200\n"
    "            elif self.db_conn:\n"
    "                try:\n"
    "                    spy_df = await asyncio.to_thread(\n"
    "                        pd.read_sql_query,\n"
    '                        "SELECT close FROM ohlcv WHERE symbol=\'SPY\' AND timeframe=\'1d\' "\n'
    '                        "ORDER BY timestamp DESC LIMIT 250",\n'
    "                        self.db_conn,\n"
    "                    )\n"
    "                    if not spy_df.empty:\n"
    '                        closes = spy_df["close"].iloc[::-1].tolist()\n'
    "                        if len(closes) >= 20:\n"
    "                            momentum = (\n"
    "                                (closes[-1] - closes[-20]) / closes[-20]\n"
    "                                if closes[-20] != 0\n"
    "                                else 0\n"
    "                            )\n"
    "                        if len(closes) >= 200:\n"
    "                            sma_200 = sum(closes[-200:]) / 200\n"
    "                            spy_above_200ma = closes[-1] > sma_200\n"
    "                            logger.debug(\n"
    '                                "True Daily SMA 200: %.2f (Price: %.2f)", sma_200, closes[-1]\n'
    "                            )\n"
    "                except Exception as e:\n"
    '                    logger.debug("Regime data fallback (1d): %s", e)\n'
    "            logger.debug(\"Regime step 'ma_check' took %.2fs\", time.perf_counter() - _t0)\n"
    "\n"
    "            breadth = 0.55\n"
    "            if self.db_conn:\n"
    "\n"
    "                def _sync_breadth() -> float:\n"
    "                    try:\n"
    "                        total = 0\n"
    "                        positive = 0\n"
    "                        major_indices = [\n"
    '                            "SPY", "QQQ", "IWM", "DIA", "XLK",\n'
    '                            "NVDA", "MSFT", "AAPL", "TSLA", "META",\n'
    "                        ]\n"
    "                        for sym in major_indices:\n"
    "                            if sym in self.last_tick_prices:\n"
    "                                total += 1\n"
    "                                positive += 1\n"
    "                            else:\n"
    "                                row = pd.read_sql_query(\n"
    '                                    "SELECT close FROM ohlcv WHERE symbol=? "\n'
    '                                    "ORDER BY timestamp DESC LIMIT 2",\n'
    "                                    self.db_conn,\n"
    "                                    params=(sym,),\n"
    "                                )\n"
    "                                if not row.empty and len(row) >= 2:\n"
    "                                    total += 1\n"
    '                                    if row["close"].iloc[0] > row["close"].iloc[1]:\n'
    "                                        positive += 1\n"
    "                        return positive / total if total > 0 else 0.55\n"
    "                    except Exception:\n"
    "                        return 0.55\n"
    "\n"
    "                breadth = await asyncio.to_thread(_sync_breadth)\n"
    "            logger.debug(\"Regime step 'breadth_check' took %.2fs\", time.perf_counter() - _t0)\n"
    "\n"
    "            regime = self.regime_classifier.classify(\n"
    "                vix=vix,\n"
    "                spy_above_200ma=spy_above_200ma,\n"
    "                breadth=breadth,\n"
    "                momentum=momentum,\n"
    "            )\n"
    "            logger.debug(\"Regime step 'classify' took %.2fs\", time.perf_counter() - _t0)\n"
    "            logger.info(\n"
    '                "Regime: %s (VIX=%.1f, Mom=%.4f, Breadth=%.2f, SPY>200MA=%s)",\n'
    "                regime, vix, momentum, breadth, spy_above_200ma,\n"
    "            )\n"
    "            # Persist for state capsule\n"
    "            self.session_restorer.save_cognitive_capsule(\n"
    "                {\n"
    '                    "regime": regime,\n'
    '                    "conviction_state": self.conviction_state,\n'
    '                    "session_pnl": self.session_pnl,\n'
    '                    "session_stats": self.session_stats,\n'
    '                    "timestamp": time.time_ns(),\n'
    "                }\n"
    "            )\n"
    "            logger.debug(\"Regime step 'capsule_save' took %.2fs\", time.perf_counter() - _t0)\n"
    "            return regime\n"
    "        except Exception as e:\n"
    '            logger.warning("Regime detection TIMEOUT/FAIL after %.2fs: %s", time.perf_counter() - _t0, e)\n'
    '            return "CHOPPY"'
)

assert OLD in content, "OLD block not found in brain_data.py"
new_content = content.replace(OLD, NEW, 1)
target.write_text(new_content, encoding="utf-8")
print("Patch applied successfully.")
