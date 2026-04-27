import sys, os, importlib, traceback
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

all_modules = [
    'vault', 'config', 'system_types', 'mind_macros', 'mind_bridge',
    'telegram_alerts', 'database_security', 'diagnostic_tracker',
    'sovereign_logic', 'mind_ultrathink', 'mind_architect', 'mind_math',
    'mind_prompts', 'mind_observer', 'mind_experiment', 'mind_evolution',
    'mind_ghost', 'mind_system',
    'coordinator', 'sovereign_decision_engine', 'swarm_predictor',
    'dms', 'watchdog', 'workload_manager', 'session_restorer',
    'memdir', 'knowledge_ingestor', 'intelligence_bus',
    'data_pipeline', 'openbb_provider', 'questdb_adapter', 'api_cache',
    'agent_a', 'agent_b', 'agent_c', 'agent_c_mt5', 'agent_d', 'agent_e',
    'ibkr_streamer', 'ollama_manager', 'exit_intelligence',
    'dhatu_oracle', 'wisdom', 'api_server', 'agent_c_ibkr'
]

print(f"=== FULL IMPORT AUDIT: {len(all_modules)} modules ===")
failures = {}
successes = 0
for mod in all_modules:
    try:
        importlib.import_module(mod)
        print(f"  OK  {mod}")
        successes += 1
    except Exception as e:
        tb = traceback.format_exc()
        root_cause = tb.strip().split('\n')[-1]
        print(f"  FAIL {mod}: {root_cause}")
        failures[mod] = tb

print()
print(f"=== RESULT: {successes} OK / {len(failures)} FAILED ===")
if failures:
    print()
    print("=== FAILURE TRACEBACKS ===")
    for mod, tb in failures.items():
        print(f"\n--- MODULE: {mod} ---")
        # Print last 15 lines of traceback
        lines = tb.strip().split('\n')
        print('\n'.join(lines[-15:]))
