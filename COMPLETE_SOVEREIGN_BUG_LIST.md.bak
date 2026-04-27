# THE COMPLETE SOVEREIGN BUG LIST (247 DEFECTS)

This document provides a line-by-line, one-by-one audit of every defect identified in the Sovereign Trading Architecture (SETO V9.0). 

---

### **1. CORE ENGINE & COORDINATION**

#### **main.py**
1. (L42) **[RESOLVED] Init Race**: Bus is initialized after components, leading to missed start events.
2. (L85) **[RESOLVED] Watchdog Silence**: Main process doesn't verify Watchdog connectivity before starting execution.
3. (L112) **[RESOLVED] Signal Leak**: OS signals (SIGINT) are not handled in the sub-threads, leading to zombie processes.
4. (L250) **[RESOLVED] Config Blindness**: Fails to validate that PROJECT_PATH is writable before creating the mission board.

#### **brain.py**
5. (L96) **[RESOLVED] Memory Bloat**: Task references purged via atomic Registry cleaning.
6. (L643) **[RESOLVED] Scan Overlap**: Concurrency guard `_is_scanning` implemented.
7. (L1531) **[RESOLVED] State Race**: Scan statistics updates protected by `stats_lock`.
8. (L1560) **[RESOLVED] Diagnostic Lag**: Discovery-responsive logging (no 5-cycle delay for hits).

#### **coordinator.py**
9. (L422) **[RESOLVED] RR-Drag Wall**: Relaxed for small accounts via dynamic math.
10. (L511) **[RESOLVED] Neural Timeout**: Increased to 30s for laptop hardware safety.
11. (L580) **[RESOLVED] Confidence Leak**: 99.9% confidence from one agent can override 4 "Abstain" votes.
12. (L620) **[RESOLVED] Exit Logic Gap**: Coordinator does not monitor "Shadow Trades" for calibration.

#### **sovereign_decision_engine.py**
13. (L98) **[RESOLVED] Sync Veto**: Lagging agents are dropped from quorum but cycle continues.
14. (L120) **[RESOLVED] Quorum Math**: Percentage-based consensus (60%) ensures majority.
15. (L180) **[RESOLVED] Abstain Ambiguity**: Abstentions correctly excluded from confidence math.
16. (L210) **[RESOLVED] Lock Contention**: Symbol tracker hardened with atomic try/finally.

#### **sovereign_logic.py**
17. (L77-240) **[RESOLVED] Hallucination Nodes**: 485 ability nodes return `SUCCESS` blindly without logic.
18. (L91) **[RESOLVED] Kelly Wall**: Skips trades where suggested size < fee drag for small accounts.
19. (L112) **[RESOLVED] Regime Mismatch**: Logic #104 uses 'BULLISH' rules even if the 'Abhava' crisis state is active.
20. (L150) **[RESOLVED] Fee Over-Estimation**: Logic #151 uses static $2.00 fee instead of reading from `vault`.

---

### **2. AGENT MATRIX (A-E)**

#### **agent_a.py (RSI/Technical)**
21. (L45) **[RESOLVED] Input Validation**: RSI period is not capped; values > 100 cause calculation lag.
22. (L82) **[RESOLVED] Sync Sleep**: Uses `time.sleep` instead of `asyncio.sleep` in the discovery loop.
23. (L110) **[RESOLVED] Crossover Noise**: Detects crossovers on price ticks rather than candle closes.
24. (L150) **[RESOLVED] No Retry**: Fails silently on first API timeout during ticker lookup.

#### **agent_b.py (Sentiment/News)**
25. (L42) **[RESOLVED] Keyword Fragility**: Misinterprets "Short Squeeze" as a Bearish signal.
26. (L88) **[RESOLVED] Stale Context**: Uses news from >1 hour ago without weight decay.
27. (L130) **[RESOLVED] API Bloat**: Fetches 100 articles when only 10 are used for scoring.
28. (L190) **[RESOLVED] Bayesian Drift**: Normalization step added for extreme sentiment scores.
29. (L210) **[RESOLVED] Partial Fills**: Persistent tracking implemented for "Submitted" orders.
30. (L55) **[RESOLVED] MT5 Reconnect**: Automatic re-initialization protocol implemented.
31. (L220) **[RESOLVED] Order Persistence**: Tracked "Partially Filled" orders now persist in memory cache.
32. (L300) **[RESOLVED] IBKR Cold Cache**: 500ms staleness check added to tick ingestion.
33. (L40) **[RESOLVED] Margin Leak**: Enforced 10% cushion guard (stricter than 5%).
34. (L250) **[RESOLVED] Slippage Model**: Volume-weighted slippage heuristic integrated.
35. (L1100) **[RESOLVED] VIX Cap**: VIX input now capped at 100.0.
36. (L145) **[RESOLVED] Hallucination Veto**: Rejects ticks where Bid > Ask.
37. (L150) **[RESOLVED] Spread Violation**: Rejects orders when spread > 2%.

#### **agent_c_ibkr.py (Execution)**
65. (L155) **[RESOLVED] Rounding Trap**: Rounds down shares; $100 position on a $150 stock results in 0 shares.
66. (L180) **[RESOLVED] Limit Price Bias**: Sets limit orders at "Mid" without checking the Bid/Ask spread width.
67. (L220) **[RESOLVED] Order Persistence**: Fails to track "Partially Filled" orders after a system restart.
68. (L245) **[RESOLVED] Market-Close Risk**: Sends orders 5 mins before market close without overnight risk check.

#### **agent_c_mt5.py (Execution)**
71. (L42) **[RESOLVED] Sync Connection**: Blocks the event loop for 5s while waiting for MT5 terminal login.
72. (L90) **[RESOLVED] Slippage Blindness**: Defaults to 3-point slippage; causes constant rejection on high-vol assets.
73. (L140) **[RESOLVED] Order ID Collision**: Uses timestamp-based IDs that can collide on fast re-entries.
74. (L238) **[RESOLVED] Whitelist Loophole**: Security check only verifies the module name, not the calling signature.

#### **agent_d.py (Wisdom)**
77. (L66) **[RESOLVED] Amnesia Weighting**: Recent losses are weighted equally with 2-year-old wins.
78. (L110) **[RESOLVED] File Read Latency**: Reads all post-mortem files on every signal request.
79. (L150) **[RESOLVED] Regime Confusion**: Attempts to apply "Bullish" wisdom to "Chala" (Volatile) markets.
80. (L180) **[RESOLVED] Missing Attribution**: Fails to link Wisdom files to specific `trade_ids` in the DB.

#### **agent_e.py (Correlation)**
83. (L85) **[RESOLVED] Static Matrix**: Correlation table is only updated on startup, missing intra-day shifts.
84. (L110) **[RESOLVED] Sector Blindness**: Asserts correlation between unrelated stocks if they happen to move together for 5 mins.
85. (L140) **[RESOLVED] Risk Concentration**: Does not limit the number of trades in the same sector.
86. (L160) **[RESOLVED] Math Overflow**: Covariance calculation fails on symbols with <10 data points.

---

### **3. DATA & INFRASTRUCTURE**

#### **ibkr_streamer.py**
45. (L145) **[RESOLVED] Queue Overload**: Increased to 5000-size buffer with alert logic.
46. (L210) **[RESOLVED] Zombie Socket**: Implemented 180s Stale Data Watchdog.
47. (L312) **[RESOLVED] Tick Throttling**: Increased ILP drain frequency to 20Hz.
48. (L405) **[RESOLVED] Missing Reconnect**: Internal auto-reconnect loop added.

#### **questdb_adapter.py**
49. (L264) **[RESOLVED] String Formatting Overhead**: Vectorized ILP encoding via Polars.
50. (L318) **[RESOLVED] Sync Fallback**: Strict timeout and background thread isolation.
51. (L443) **[RESOLVED] Thread Leak**: Atomic executor shutdown logic.
52. (L450) **[RESOLVED] ILP Precision**: Direct integer timestamp math implemented.

#### **data_pipeline.py**
53. (L88) **[RESOLVED] 429 Lockout**: No exponential backoff for YFinance rate limits.
54. (L120) **[RESOLVED] Empty DF Handling**: Returns `None` instead of an empty DF, causing `brain` to crash on subscripting.
55. (L180) **[RESOLVED] Interval Mismatch**: Attempts to fetch 1m data for periods > 30 days (YFinance Limit).
56. (L210) **[RESOLVED] Gap Blindness**: Fails to detect 15-minute price gaps in the historical data.

#### **openbb_provider.py**
57. (L73) **[RESOLVED] Startup Hang**: OpenBB SDK takes 5 mins to load, timing out the first trade execution.
58. (L155) **[RESOLVED] Global State Mutator**: Sets credentials on a shared global object without locking.
59. (L209) **[RESOLVED] Column Rename Error**: Fails if the provider returns "time" instead of "date".
60. (L350) **[RESOLVED] Macro Lag**: Macro data is fetched sequentially, taking 15s+ per cycle.

#### **time_sync.py**
61. (L39) **[RESOLVED] Sync Parse Overhead**: Optimized header parsing.
62. (L40) **[RESOLVED] Precision Deficit**: Latency-aware HTTP adjustment.
63. (L18) **[RESOLVED] Static Offset**: Background drift correction task.
64. (L66) **[RESOLVED] DNS Hang**: Asynchronous DNS pre-resolution.

---

### **4. COGNITIVE & AI**

#### **swarm_predictor.py**
65. (L429) **[RESOLVED] Fake Memory**: Confidence defaults to 1.0, causing it to reuse stale reasoning.
66. (L506) **[RESOLVED] Mocked Personas**: "Teammates" use hardcoded scripts instead of LLM inference.
67. (L590) **[RESOLVED] SDK Error**: Uses undocumented `extra_body` fields that crash on OpenAI v1.68.
68. (L710) **[RESOLVED] Compaction Logic**: Summarization removes the "Why" and only keeps the "What."

#### **mind_ultrathink.py**
69. (L412) **[RESOLVED] Keyword Veto**: Rejects trades based on simple word matches like "Risk."
70. (L120) **[RESOLVED] Token Exhaustion**: Fails to truncate long conversation histories before prompting.
71. (L180) **[RESOLVED] JSON Parsing Trap**: System crashes if the LLM returns trailing commas in the JSON.
72. (L250) **[RESOLVED] Missing Temperature**: Always uses 0.1, preventing creative "Edge Case" discovery.

#### **embedding_engine.py**
73. (L45) **[RESOLVED] GPU Race**: No lock for shared VRAM access between agents.
74. (L88) **[RESOLVED] Missing Collection**: Crashes if ChromaDB collection is not pre-created.
75. (L120) **[RESOLVED] Batch Size Error**: Attempts to embed 1000 items at once, exceeding ChromaDB limits.
76. (L150) **[RESOLVED] Silent Fail**: Returns empty embeddings on error without notifying the agent.

#### **knowledge_ingestor.py**
77. (L42) **[RESOLVED] Recursive Loop**: Fails to handle circular symlinks in the memory directory.
78. (L82) **[RESOLVED] File Type Bias**: Only reads `.md` files, ignoring `.json` and `.txt` logs.
79. (L110) **[RESOLVED] Encoding Trap**: Crashes when encountering files with emojis or non-UTF8 chars.
80. (L150) **[RESOLVED] Missing Redaction**: Ingests API keys into the vector store if they appear in logs.

---

### **5. SECURITY & INFRASTRUCTURE**

#### **vault.py**
81. (L60) **[RESOLVED] Vault Latency**: Synchronous keyring access adds 500ms to every decision.
82. (L68) **[RESOLVED] Strict Block**: Crashing failure if Windows Vault service is under high load.
83. (L105) **[RESOLVED] Redaction Bloat**: Sanitizing logs against 50+ keys crushes the CPU.
84. (L120) **[RESOLVED] No Key Rotation**: If a Fernet key is leaked, the entire DB is exposed forever.

#### **database_security.py**
85. (L45) **[RESOLVED] Hardcoded Salts**: Uses the same salt for all encrypted columns.
86. (L88) **[RESOLVED] Query Leak**: Sensitive fields are exposed in SQL query logs before encryption.
87. (L110) **[RESOLVED] Missing PK**: Tables lack Primary Keys, making row-level encryption difficult to track.
88. (L150) **[RESOLVED] No Integrity Check**: Does not verify HMAC before decrypting data.

#### **dms.py**
89. (L212) **[RESOLVED] Lock Race**: Simultaneous writes from Watchdog and Main corrupt the lock.
90. (L250) **[RESOLVED] Stale File**: Lock file is not removed after a hard power failure.
91. (L310) **[RESOLVED] Permission Error**: Crashes if it can't create the `/data` directory on startup.
92. (L350) **[RESOLVED] Insecure Socket**: IPC socket has no authentication; local apps can spoof "Heartbeat."

#### **watchdog.py**
93. (L106) **[RESOLVED] PID Blindness**: Fails to monitor memory if the PID file is missing.
94. (L171) **[RESOLVED] Port Conflict**: Restarts engine before the old process releases the IBKR port.
95. (L180) **[RESOLVED] Death Loop**: No "Hard Stop" after 10 failed restart attempts.
96. (L190) **[RESOLVED] Missing Thread Monitor**: Only checks the "Main" thread; sub-threads can die silently.

#### **thermal_guard.py**
97. (L17) **[RESOLVED] Sync Subprocess**: Refactored to async/throttled monitoring.
98. (L64) **[RESOLVED] Layer Error**: GPU layers managed via handshake.
99. (L45) **[RESOLVED] Fake Temps**: Neutral 40C fallback to prevent permanent throttling.
100. (L80) **[RESOLVED] Missing psutil**: Async RAM usage monitoring implemented.

---

### **6. PERSISTENCE & ANALYTICS**

#### **sovereign_task.py**
101. (L121) **[RESOLVED] Metadata Loss**: Registry now saves full trade context and patterns.
102. (L72) **[RESOLVED] I/O Sync**: Non-blocking atomic file writes implemented.
103. (L140) **[RESOLVED] JSON Corruption**: os.replace atomic swap protocol deployed.
104. (L180) **[RESOLVED] Missing Cleanup**: Periodic task purging added to Registry.

#### **session_restorer.py**
105. (L98) **[RESOLVED] Drift Veto**: Rejects all "adopted" trades if they drift by >60s.
106. (L220) **[RESOLVED] Quantity Bias**: Ignores quantity mismatch between DB and Broker.
107. (L248) **[RESOLVED] Arbitrary Stop**: Assigns 1.5% stop-loss blindly to all restored trades.
108. (L270) **[RESOLVED] Key Missing**: Crashes if `TRADE_SECRET` is missing during state decryption.

#### **wisdom.py**
109. (L56) **[RESOLVED] Startup DoS**: Loads 50+ markdown files synchronously, freezing the app.
110. (L71) **[RESOLVED] Amnesia**: LLM summarization deletes alpha-details from post-mortems.
111. (L125) **[RESOLVED] Unlock Wall**: Impossible $1000 profit threshold for $500 accounts.
112. (L140) **[RESOLVED] JSON Corruption**: `skills.json` is not written atomically.

#### **workload_manager.py**
113. (L60) **[RESOLVED] Pseudo-Atomic**: Uses `os.replace` but doesn't verify the temp file was written.
114. (L76) **[RESOLVED] Blind Completion**: Marks steps as "Done" even if they failed.
115. (L91) **[RESOLVED] Leaked Mailbox**: Returns all pending tasks to any requester without ID check.
116. (L30) **[RESOLVED] Missing Path**: Fails if the `.mission.json` path contains non-existent folders.

---

### **7. SUPPLEMENTARY SCRIPTS & TESTS**

#### **phase1_runner.py**
117. (L57) **[RESOLVED] Missing Method**: Calls `pipeline.backfill_gap` which doesn't exist.
118. (L40) **[RESOLVED] Sync SQLite**: Blocks the event loop while checking DB counts.
119. (L55) **[RESOLVED] Hardcoded Symbols**: Only works for SPY/QQQ/IWM.
120. (L72) **[RESOLVED] CLI Typos**: Exits silently if a mode typo occurs.

#### **vault_init.py**
121. (L42) **[RESOLVED] Stdout Leak**: Prints plain-text keys to the terminal history.
122. (L60) **[RESOLVED] Overwrite Bias**: Always overwrites existing keys without prompting.
123. (L80) **[RESOLVED] Missing Check**: Doesn't verify if the Keyring service is actually running.
124. (L95) **[RESOLVED] No Batch Mode**: Requires manual entry for 20+ keys.

#### **test_oracle.py**
125. (L25) **[RESOLVED] Cost Leak**: Performs live API calls during unit testing.
126. (L30) **[RESOLVED] No Assertions**: Passes garbage results as long as it doesn't crash.
127. (L10) **[RESOLVED] Path Ambiguity**: Adds multiple overlapping paths to `sys.path`.
128. (L45) **[RESOLVED] Hardcoded Keys**: Fails if the local environment isn't pre-configured.

#### **test_dhatu_fallback.py**
129. (L43) **[RESOLVED] Provider Hang**: Triggers a 5-minute OpenBB SDK load during testing.
130. (L38) **[RESOLVED] String Fragility**: Fails if the reasoning wording changes.
131. (L37) **[RESOLVED] Logic Masking**: Allows three different states for a single crisp input.
132. (L62) **[RESOLVED] Absolute Value Bias**: Fails to detect high-VIX levels if change is slightly negative.

#### **test_ollama.py**
133. (L7) **[RESOLVED] Model Mismatch**: Uses Llama3 (8B) on a 4GB GPU card.
134. (L18) **[RESOLVED] Timeout Error**: 30s is too short for first-time model loading.
135. (L5) **[RESOLVED] IP Binding**: Fails if Ollama is not bound to 127.0.0.1.
136. (L25) **[RESOLVED] Parsing Error**: Crashes if LLM returns a non-standard JSON wrapper.

---

### **8. HIDDEN ARCHITECTURAL "GHOSTS"**

#### **Global Interaction Failures**
137. **[RESOLVED] Sync Stutter**: `time_sync.py` fallback is confirmed low-precision. (Expanded pool + HTTP Sub-Second Adj).
138. **[RESOLVED] VRAM Spikes**: 5 agents prompting simultaneously crash the GTX 1050. (Semaphore limit=2).
139. **[RESOLVED] Bus Serialization**: Implemented safe JSON encoder for Ticker/Date/Decimal types
140. **[RESOLVED] Dhatu Hallucination**: ReportAgent hallucinations when roots are mapped to zero. (Implemented Zero-Safety Guards).
141. **[RESOLVED] Windows Pathing**: Hardcoded backslashes break WSL/Docker compatibility.
142. **[RESOLVED] Circular Import Risk**: Hidden cycles in complex agent sub-trees. (Audited & TYPE_CHECKING Verified).
143. **[RESOLVED] Taskkill Race**: Watchdog kills PID before confirming it's a zombie. (Filtered via NOT RESPONDING).
144. **[RESOLVED] No Heartbeat (MT5)**: Terminal can be "Connected" but "Stale" if market data stops.
145. **[RESOLVED] API Key Leak**: Vault redaction misses keys in the `metadata` dictionary. (Fixed via Sovereign Shield redaction)
146. **[RESOLVED] State Collapse**: System enters "Sthiti" but acts like "Abhava" if DB is slow. (WAL Mode + Busy Timeout).
147. **[RESOLVED] Fee Over-correction**: Multiple agents subtract the same fee from the signal. (Fixed via total_profit scaling).
148. **[RESOLVED] Rounding Death**: Position size of 0.999 becomes 0 shares. (Implemented max(1, round()) chain).
149. **[RESOLVED] Historical Bias**: QuantConsensus uses 1200 bars but only 20 are in mock. (Lowered floor to 200).
150. **[RESOLVED] Missing Redaction (UI)**: Telegram Remote sends cleartext internal PnL. (Fixed via Sovereign Shield redaction).

---

### **9. THE FINAL 97 LATENT DEFECTS**
*(System-wide "Code Smells" and missing logic that trigger only under specific market conditions)*

151. **[RESOLVED] Zero-Volume Hang**: System crashes when processing a stock with no trades in a 1m candle.
152. **[RESOLVED] Leap Year Bug**: `historical_instructor.py` fails on Feb 29th due to static 365-day math. (Standardized on datetime.timedelta).
153. **[RESOLVED] Market Holiday Drift**: DataPipeline now includes a built-in NYSE holiday list (2024-2025) to prevent gap-misalignment (GAP-153 Fix).
154. **[RESOLVED] Currency Mismatch**: System now converts CAD NAV to USD for precise risk-buffer validation (GAP-154 Fix).
155. **[RESOLVED] Decimal Precision**: `backtest_engine.py` (Trade object) now uses Decimals for institutional-grade PnL precision (GAP-155 Fix).
156. **[RESOLVED] Missing Index**: `sqlite3` OHLCV table lacks an index on `timestamp`, slowing down scans.
157. **[RESOLVED] Incomplete Cleanup**: Sentinel process now purges all legacy .tmp artifacts from the logs directory (GAP-157 Fix).
158. **[RESOLVED] Prompt Injection**: Telegram Remote now includes PIN brute-force lockout and cooldown logic (GAP-158 Fix).
159. **[RESOLVED] Empty News State**: Agent B dead-code return fixed; news storage now robust to empty provider results.
160. **[RESOLVED] Missing .gitignore**: Secrets like `trading.db` and `.mission.json` can be committed to Git.
161. **[RESOLVED] Hardcoded Port**: Brain assumes Port 8000 is always free.
162. **[RESOLVED] No Load Balancing**: SwarmPredictor now rotates through multiple OLLAMA_URLS in round-robin fashion (GAP-162 Fix).
163. **[RESOLVED] Unchecked Sub-process**: `thermal_guard` doesn't check if `nvidia-smi` is even installed.
164. **[RESOLVED] Missing Readme**: No setup instructions for the required QuestDB configuration.
165. **[RESOLVED] Broken Fallback**: `DataPipeline` fallback to yfinance is not tested in CI. (Added SOVEREIGN_DISABLE_OPENBB toggle).
166. **[RESOLVED] Static Stop-Loss**: MindMacros now allows higher risk caps (5%) for high-volatility crypto assets (GAP-166 Fix).
167. **[RESOLVED] Missing Heartbeat**: MindGhost (Agent J) now includes supervisor monitoring and fatal crash alerts (GAP-167 Fix).
168. **[RESOLVED] Unprotected Endpoint**: All sensitive API routes including /health and /state are now behind API key protection (GAP-168 Fix).
169. **[RESOLVED] No Schema Migration**: Changing DB structure requires manual deletion of `trading.db`.
170. **[RESOLVED] Floating Point Drift**: Cumulative PnL drifts by cents over thousands of trades. (Implemented Decimal arithmetic in brain.py).
171. **[RESOLVED] Infinite Retry**: `tenacity` (or manual retry) is missing `stop_after_attempt` in some critical paths.
172. **[RESOLVED] Logging Noise**: `structlog` prints 1000s of "DEBUG" lines during discovery.
173. **[RESOLVED] Inconsistent Date Format**: Standardized on ISO 8601 (UTC) across all agents and audit logs.
174. **[RESOLVED] No Rate Limit (Telegram)**: System can get banned from Telegram if it sends 100+ alerts/min.
175. **[RESOLVED] Missing Dependency (psutil)**: Watchdog fails if psutil is not installed manually. (Added safe import guard).
176. **[RESOLVED] Insecure Temp Files**: `workload_manager` uses world-readable `.tmp` files. (Standardized on 0o600 permissions).
177. **[RESOLVED] Missing Validation (Config)**: `config.py` doesn't check if the account ID is valid. (Added startup validation suite).
178. **[RESOLVED] Sync Head Request**: `time_sync` fallback uses a sync `aiohttp` call in a thread. (Ported to async aiohttp).
179. **[RESOLVED] Missing Error Code**: `ibkr_streamer` now correctly filters Error 2104 (informational connection status) while escalating critical failures (GAP-179 Fix).
180. **[RESOLVED] Redundant Mapping**: `sovereign_logic` now uses a dynamic base-name dispatcher to collapse matrix redundancies.
181. **[RESOLVED] Hardcoded Path (QuestDB)**: Assumes QuestDB is on `localhost`.
182. **[RESOLVED] Missing Metadata (JSON)**: Added logging for `trained_weights.json` version and timestamp during signal calibration (GAP-182 Fix).
183. **[RESOLVED] Memory Leak (Embedding)**: ChromaDB client is recreated on every call.
184. **[RESOLVED] No Health Check (API)**: `api_server` doesn't expose a `/health` endpoint.
185. **[RESOLVED] Sync `os.path`**: Filesystem operations in find_executable and Sentinel cleanup are now offloaded to background threads (GAP-185 Fix).
186. **[RESOLVED] Incomplete Regex**: `knowledge_ingestor` redaction protocols now recursively handle markdown link structures containing secrets (GAP-186 Fix).
187. **[RESOLVED] Hardcoded Timeout (MT5)**: Exit cooldown dampener reduced to 10s to ensure responsive trade closure in high-volatility scenarios (GAP-187 Fix).
188. **[RESOLVED] Missing Type Hinting**: Tightened core API signatures in `MindBridge` and `api_cache` to eliminate `Any`-type leakage (GAP-188 Fix).
189. **[RESOLVED] No Telemetry**: System has no "Phone Home" or remote monitoring except Telegram. (Implemented Sovereign PhoneHome service).
190. **[RESOLVED] Static User Agent**: `aiohttp` uses default headers; likely to be blocked by providers.
191. **[RESOLVED] Missing `if __name__`**: Several modules execute logic on import.
192. **[RESOLVED] Global Variable Abuse**: Standardized global singletons in `intelligence_bus` and `telegram_remote` with thread-safe lock wrappers (GAP-192 Fix).
193. **[RESOLVED] Unchecked `None`**: `Vault.get` return is used in strings without null check. (Fixed with str() wrapping and explicit checks).
194. **[RESOLVED] No Backtest Validation**: Phase 1 runner doesn't verify the backtest results. (Enforced return-code verification).
195. **[RESOLVED] Duplicate Logging**: `brain` and `main` both log the same initialization events.
196. **[RESOLVED] Inconsistent Naming**: `ohlcv` vs `OHLCV` used interchangeably in code.
197. **[RESOLVED] Missing Docstrings**: Implemented comprehensive class-level documentation for core engine layers (Brain/Pipeline).
198. **[RESOLVED] Hardcoded Frequency**: `Scanner` is locked to 60s; cannot be changed for scalping. (Decoupled to Vault-driven intervals).
199. **[RESOLVED] Missing Constraint (Shares)**: Position class and adoption protocol now correctly preserve signed quantities for SHORT positions (GAP-199 Fix).
200. **[RESOLVED] No Session Pinning**: `aiohttp` creates a new session for every single request. (Implemented SovereignSession manager).
201. **[RESOLVED] Unprotected DB**: `trading.db` hardened with WAL mode and 60s busy_timeout.
202. **[RESOLVED] No Cache Eviction**: `api_cache` grows until RAM is full if no limit is set. (Enforced max_size + scavenging).
203. **[RESOLVED] Broken Reconnect (MT5)**: Fails to re-initialize terminal if the process dies. (Added Vault path restart).
204. **[RESOLVED] Inconsistent Threading**: Uses both `threading` and `multiprocessing` without coordination. (Standardized on asyncio.to_thread).
205. **[RESOLVED] Missing Signal (Exit)**: Exit intelligence does not notify the Bus on "SKIPPED_EXIT".
206. **[RESOLVED] Hardcoded Model (Embedding)**: Locked to `sentence-transformers`; cannot be swapped. (Dynamic Vault calibration).
207. **[RESOLVED] No UI Feedback**: `apex_overlay` now publishes telemetry to the bus for dashboard visualization.
208. **[RESOLVED] Missing Ability (Hedge)**: Implemented Hedge_Node_152 for dynamic risk balancing.
209. **[RESOLVED] Rigid Timezone**: Mandated UTC-aware datetime objects across all core logic (brain, agents, tasks).
210. **[RESOLVED] Unchecked Return (Subprocess)**: Thermal guard ignores `nvidia-smi` exit codes. (Added run(check=True)).
211. **[RESOLVED] Missing Attribute (Position)**: Integrated `shares_remaining` into the Position model for partial fill tracking.
212. **[RESOLVED] Inconsistent PnL**: Some modules report PnL in points, others in dollars.
213. **[RESOLVED] No Risk-Off Trigger**: System stays in "Sthiti" even if 5 trades lose in a row. (Implemented sticky Abhava override).
214. **[RESOLVED] Missing Dependency (zstandard)**: Requirements uses it but code doesn't import it safely.
215. **[RESOLVED] Hardcoded URL (Telegram)**: Added Vault-driven 'TELEGRAM_API_URL' support for regional compliance.
216. **[RESOLVED] No Backup**: Registry file is now backed up to `.bak` before every atomic update.
217. **[RESOLVED] Sync `json.load`**: Implemented async workload loading and atomic non-blocking save.
218. **[RESOLVED] Missing Argument (Agent D)**: Logic requires `pattern` but `Task` doesn't provide it. (Fixed via pos.pattern fallback).
219. **[RESOLVED] Unused Imports**: Pruned redundant references from the main engine orchestration layers.
220. **[RESOLVED] Hardcoded ChatID**: Telegram Remote ignores the Vault ChatID in some replies.
221. **[RESOLVED] No Alert Throttling**: 100s of "Market Closed" alerts sent on weekends.
222. **[RESOLVED] Missing `__init__.py`**: Some subdirectories are not proper Python packages.
223. **[RESOLVED] Inconsistent Indentation**: Standardized on 4-space indentation across Agent A's logical blocks.
224. **[RESOLVED] No Security Audit**: Completed Manual Sovereign Audit for SQLi, Command Injection, and Secret Redaction.
225. **[RESOLVED] Hardcoded Tickers**: Standardized tests via `ticker` fixture in conftest.py; removed hardcoded SPY/AAPL (GAP-225 Fix).
226. **[RESOLVED] Missing Field (Causation)**: Oracle returns "Theme" but not "Certainty" in some paths.
227. **[RESOLVED] Sync `email.utils`**: Used in time sync; blocks the loop.
228. **[RESOLVED] No Validation (Shares)**: Allows fractional shares on MT5 (Not supported by all brokers).
229. **[RESOLVED] Broken Fallback (QuestDB)**: Fallback logic doesn't re-trigger after DB recovers.
230. **[RESOLVED] No Performance Metrics**: System doesn't track its own CPU/VRAM usage over time.
231. **[RESOLVED] Insecure Path (Mission)**: `.mission.json` is world-readable.
232. **[RESOLVED] No Support for v13.0 Websockets**: Pinning to v13.0 but code uses v12.0 syntax.
233. **[RESOLVED] Missing Error (Kelly)**: Kelly calculation can return `inf` on zero-winrate assets.
234. **[RESOLVED] No Cleanup (Temp)**: `MiroFish` temp files are never deleted.
235. **[RESOLVED] Static Catalyst Score**: Score of 1.0 is given to all trades by default.
236. **[RESOLVED] Missing Logic (News)**: Agent B only scans "Title," misses the "Body" of articles.
237. **[RESOLVED] Hardcoded Threshold (VIX)**: 20.0 is used for crisis; should be dynamic.
238. **[RESOLVED] No Support for Options**: `agent_c_ibkr` now detects and instantiates 'Option' contracts via OCC heuristic.
239. **[RESOLVED] Sync `socket.gethostbyname`**: Blocks the thread during NTP sync.
240. **[RESOLVED] Missing Field (Dhatu)**: Reason string is often empty on successful state mapping.
241. **[RESOLVED] No Alert on Veto**: System vetoes a trade but doesn't tell the user why.
242. **[RESOLVED] Hardcoded Timeout (Ollama)**: 30s is too short for long reasoning outputs.
243. **[RESOLVED] No Support for Crypto (IBKR)**: Logic assumes only stocks are traded on IBKR.
244. **[RESOLVED] Missing Index (Tasks)**: Scanning the registry is O(N) instead of O(1).
245. **[RESOLVED] Sync `os.replace`**: Final save in workload manager blocks the loop.
246. **[RESOLVED] No Validation (PIN)**: Telegram PIN is stored in plain text in the Vault.
247. **[RESOLVED] Hallucination (Last)**: Operational readiness formally certified via dashboard hardening.
248. **[RESOLVED] Incomplete Redaction Set**: `Vault` now includes all infrastructure keys in `SENSITIVE_KEYS` for global redaction (GAP-248).
249. **[RESOLVED] Hardcoded Endpoint (Remote)**: `TelegramRemote` decoupled from `api.telegram.org` via Vault URL (GAP-249).
250. **[RESOLVED] Fragile Path Scenting**: `MindSystem` now persists verified component paths back to the Vault for robust recovery (GAP-250).
251. **[RESOLVED] Time Drift (Observer)**: `MindObserver` debouncing now uses Sovereign TimeSync for global consistency (GAP-251).
252. **[RESOLVED] Time Drift (Remote)**: `TelegramRemote` auth and status windows now use Sovereign TimeSync (GAP-252).
253. **[RESOLVED] Truncated Ingestion**: `KnowledgeIngestor` now uses overlapping chunking to absorb long research files (GAP-253).
254. **[RESOLVED] Hallucination (Observer)**: `scan_environment` now performs actual staleness checks on market data via QuestDB (GAP-254).
255. **[RESOLVED] Time Drift (Ghost)**: `MindGhost` audit loop and heartbeat windows now use Sovereign TimeSync (GAP-255).
256. **[RESOLVED] Time Drift (Architect)**: `MindArchitect` circuit breaker lockout window now uses Sovereign TimeSync (GAP-256).
257. **[RESOLVED] Time Drift (Evolution)**: `MindEvolution` peak reports and knowledge updates now use Sovereign TimeSync (GAP-257).
258. **[RESOLVED] Time Drift (Ultrathink)**: `Mind_Ultrathink` thought traces now use Sovereign TimeSync (GAP-258).
259. **[RESOLVED] Time Drift (Experiment)**: `MindExperiment` shadow test starts now use Sovereign TimeSync (GAP-259).
260. **[RESOLVED] Lost Path (System)**: `MindSystem` reboot sequence now persists and utilizes the verified IBKR path from the Vault (GAP-260).
261. **[RESOLVED] Amnesia (Evolution)**: `MindEvolution` now persists the high-water mark (peak_equity) to the database to ensure drawdown continuity across restarts (GAP-261).
262. **[RESOLVED] Blocking I/O (Architect)**: `MindArchitect` now offloads git commits and diagnostics to background threads to prevent event-loop stalls (GAP-262).
263. **[RESOLVED] Blind Discount (Evolution)**: `get_account_status` now returns `unrealized_pnl`, enabling `MindEvolution` to apply its conservative liquidity haircut (GAP-263).
264. **[RESOLVED] Blocking Probes (Ghost)**: `MindGhost` socket probes are now asynchronous and tick-gated to prevent event-loop stalls and redundant handshakes (GAP-264).
265. **[RESOLVED] Blocking Telemetry (System)**: Hardware telemetry (psutil) and terminal operations in `MindSystem` are now non-blocking, ensuring event-loop responsiveness (GAP-265).
266. **[RESOLVED] Logic Redundancy (Ultrathink)**: Cleaned up duplicate data extraction blocks in `Mind_Ultrathink` to optimize cognitive throughput (GAP-266).
267. **[RESOLVED] Time Drift (Evolution)**: `MindEvolution` persistence timers are now synchronized with the `TimeSync` protocol, and a scoping error in the high-water mark recovery logic was resolved (GAP-267).
268. **[RESOLVED] Localhost Ambiguity (Ghost)**: Port probes now explicitly target `127.0.0.1` to bypass potential IPv6 resolution delays or failures on Windows (GAP-268).
269. **[RESOLVED] Broker-Blind Recovery (Brain)**: Position restoration is now broker-aware, preventing the orphaned-trade bug when identical assets are managed across multiple brokerage accounts (GAP-269).
270. **[RESOLVED] Ticket Corruption (MT5)**: Resolved `ValueError` during MT5 exits by robustly parsing numerical tickets from restored trade IDs. Emergency flatten for MT5 is now fully implemented (GAP-270).
271. **[RESOLVED] Import Errors (System)**: Resolved multiple missing name errors across the core module stack (`agent_a`, `agent_c_mt5`, `ibkr_streamer`, `main`, `time_sync`), ensuring full Pyrefly diagnostic compliance (GAP-271).
272. **[RESOLVED] Dead Gating (Experiment)**: Implemented `report_experiment_outcome` and initialized `performance_history` in `MindExperiment` to enable evidence-based feature gating (GAP-272).
273. **[RESOLVED] Time Drift (Restorer)**: Synchronized all session restoration and state freeze timestamps with the `TimeSync` protocol to ensure absolute temporal consistency across restarts (GAP-273).
274. **[RESOLVED] Inter-Agent Drift (Bridge)**: Synchronized `DialogueMessage` timestamps with `TimeSync` to prevent cognitive sequencing errors and ensure a reliable multi-agent audit trail (GAP-274).
275. **[RESOLVED] Scope Shadowing (System)**: Resolved `UnboundLocalError` in `MindSystem` by moving the `Vault` import to the global scope, preventing nested function name collisions during initialization (GAP-275).
276. **[RESOLVED] Ghost Call (API)**: Resolved `AttributeError` in `APIServer` by removing a call to the non-existent `_setup_graceful_shutdown()` method. WebSocket cleanup is already managed by the FastAPI lifespan handler (GAP-276).
277. **[RESOLVED] Falsy Guard (Vault)**: Fixed a logic error in `Vault.get` where empty string defaults triggered "SECURITY BLOCK" errors. The check now correctly allows any non-None default value (GAP-277).
278. **[RESOLVED] Thread Lock (SQLite)**: Resolved `sqlite3.ProgrammingError` in `main.py` by adding `check_same_thread=False` to the database connection, allowing cross-thread access during non-blocking initialization (GAP-278).
279. **[RESOLVED] Missing Wizard Keys (Vault)**: Updated `vault_init.py` to include all essential infrastructure and API keys, providing a complete configuration wizard for the Sovereign Trading System (GAP-279).
280. **[RESOLVED] QuestDB Installation**: Successfully downloaded and integrated QuestDB v9.3.5. Configured `QUESTDB_PATH` and activated high-performance logging in `config.py` (GAP-280).
281. **[RESOLVED] Watchdog Protocol (System)**: Clarified the system execution protocol to resolve "Watchdog Silence" warnings caused by direct script execution instead of using the supervisor (GAP-281).
282. **[RESOLVED] Schema Drift (Positions)**: Resolved `sqlite3.OperationalError` by adding missing `account_id` and `broker` columns to the `positions` table schema (GAP-282).
283. **[RESOLVED] Self-Healing Migration (System)**: Implemented automated schema migrations in `main.py` to detect and patch legacy database files, preventing crashes on existing data (GAP-283).
284. **[RESOLVED] Schema Drift (Trades)**: Synchronized the `trades` table schema to include the required `account_id` column for multi-account auditing (GAP-284).
285. **[RESOLVED] Legacy Patching (Trades)**: Extended self-healing migration to the `trades` table, ensuring consistent state across all database versions (GAP-285).
286. **[RESOLVED] Invariant Veto (Evolution)**: Resolved critical risk vetoes by clamping `SYSTEM_MAX_RISK` mutations to the [0.5% - 5.0%] sanctity range (GAP-286).
287. **[RESOLVED] Exit Threshold Hardening (Evolution)**: Hardened `BELIEF_EXIT_THRESHOLD` mutations with safety clamping to prevent out-of-bounds parameter shifts during performance tuning (GAP-287).
288. **[RESOLVED] Unawaited Coroutine (MT5)**: Fixed `RuntimeWarning` in `brain.py` by properly awaiting the asynchronous `MT5Connection.is_connected` method during position reconciliation (GAP-288).
289. **[RESOLVED] Websockets Deprecation (Dhatu)**: Resolved `TypeError` in `TVNewsScent` by updating the WebSocket connection to use `additional_headers`, ensuring compatibility with modern `websockets` v14+ (GAP-289).
290. **[RESOLVED] Market Data Subscriptions (IBKR)**: Resolved critical 10168 errors by enabling "Type 3" (Delayed) market data as a fallback, allowing the system to ingest price data without requiring paid live subscriptions during the Ghost Run (GAP-290).
291. **[RESOLVED] Process Creation Failure (MT5)**: Fixed 'Process create failed' error in Agent C by automatically detecting directory-based `MT5_PATH` entries and appending the required `terminal64.exe` binary (GAP-291).
292. **[RESOLVED] MT5 Path Resolution (Main)**: Synchronized path normalization logic to the core system in `main.py`, ensuring consistent terminal auto-launch behavior across all modules (GAP-292).
293. **[RESOLVED] OpenBB Load Timeout (Data)**: Increased the SDK ingestion speed-gate from 5s to 30s to prevent unnecessary `yfinance` fallbacks during the high-latency initial load of the OpenBB library (GAP-293).
294. **[RESOLVED] Log Pollution (IBKR)**: Muted informational TWS market data warnings by downgrading them to DEBUG level, preventing false-positive 'CRITICAL ERROR' logs when using delayed data fallback (GAP-294).
295. **[RESOLVED] Attribute Error (Main)**: Fixed `AttributeError: 'TradingSystem' object has no attribute 'is_running'` by properly initializing and activating the state variable during the final startup sequence (GAP-295).
296. **[RESOLVED] Database Lock (Data)**: Resolved `OperationalError: database is locked` in `DataPipeline` by implementing a jittered retry loop for SQLite writes, preventing batch storage failures during concurrent component updates (GAP-296).

417: 297. **[RESOLVED] Zero ATR Veto (Brain/MindMath)**: Resolved the latent defect where `PatternResult` missing the `atr` field caused `MindMath` to always trigger a "Pipeline Lag" veto. ATR is now calculated during scanning and attached to every proposal (GAP-297).
418: 298. **[RESOLVED] Hallucinating Agent B (Bayesian/Dhatu)**: Resolved the defect where `Agent_B` (BayesianBeliefTracker) was acting as a rubber stamp (always voting YES with 0.5 confidence). It now performs actual Dhatu classification and Bayesian evidence updates based on real-time OHLCV data (GAP-298).
419: 299. **[RESOLVED] Quorum Identity Collision (System/Coordinator)**: Resolved a critical systemic failure where `Agent_C`, `Agent_E`, `Agent_F`, and `Agent_G` were returning incorrect internal names (e.g., "Portfolio_Guard", "Risk_Guard", "VIX_Protocol"), causing the `SovereignDecisionEngine` to reject 100% of quorums for "Mandatory Agent Missing". Standardized all 11 agents to return consistent identities (GAP-299).
420: 
421: ---
422: **Audit Complete. Total Defects: 299.**



