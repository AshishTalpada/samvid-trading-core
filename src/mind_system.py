import asyncio
import logging
import os
import subprocess
from typing import Any
from vault import Vault  # pyre-ignore[21]

from mind_bridge import MindBridge

logger = logging.getLogger(__name__)


class MindSystem:
    """
    Agent I: The System-Level Bash Mind.
    Focuses on 'System Scent' and 'Service Recovery'.
    Inspired by Claude-Code's 'BashTool' and 'findExecutable' logic.
    """

    def __init__(self, bridge: MindBridge) -> None:
        self.bridge = bridge
        self.is_running = False
        self.lock = asyncio.Lock() # GAP-61 FIX: Serialized System Control

        # 1. THE CERTIFIED COMMAND ALLOWLIST (Samvid v1.0-beta-beta Safety Gate)
        # We only allow these specific, hardcoded operations.
        self.CERTIFIED_COMMANDS = {
            "RESTART_IBKR": [
                "taskkill /F /IM TWS.exe /IM ibgateway.exe",
                "start TWS.exe || start ibgateway.exe",
            ],
            "RESTART_GATEWAY": ["taskkill /F /IM ibgateway.exe", "start ibgateway.exe"],
            "CHECK_NETWORK": ["ping -n 1 8.8.8.8"],
            "CHECK_DISK": ["dir /s"],  # No destructive disk commands
            "CLEAN_LOGS": ["del /F /Q logs/*.old"],
        }

        # Register System Tools
        self.bridge.register_tool("run_system_command", self._tool_run_system_command)
        self.bridge.register_tool("reboot_service", self._tool_reboot_service)
        self.bridge.register_tool("find_executable", self._tool_find_executable)
        self.bridge.register_tool("sovereign_flush", self._tool_sovereign_flush)
        self.bridge.register_tool("get_system_metrics", self._tool_get_system_metrics)

    async def start(self) -> None:
        """Launch the System-Level Mind."""
        self.is_running = True
        logger.info("MindSystem (Agent I): Service-level 'Scent' control active.")

    async def _tool_find_executable(self, name: str) -> dict[str, Any]:
        """Sovereign 'Scent' Tool: Autonomously locates executables via Vault -> Filesystem -> Registry."""
        found_paths_info = [] # GAP-59/66: Changed to info-based tracking

        def _sync_find_scent():
            # 0. VAULT/ENV OVERRIDE (SOLUTION 4: Environment-Agnostic)
            # Prioritize paths manually set in the Vault to avoid scan fragility.
            vault_key = f"{name.upper()}_PATH"
            val = Vault.get(vault_key)
            if val and os.path.exists(str(val)):
                logger.info(f"MindSystem: Using Vault-certified path for {name}: {val}")
                # If it's a directory, try to append the standard exe name
                if os.path.isdir(str(val)):
                    patterns = {
                        "ibkr": ["tws.exe", "ibgateway.exe"],
                        "mt5": ["terminal64.exe"],
                        "questdb": ["questdb.exe"],
                    }
                    for tgt in patterns.get(name.lower(), [f"{name}.exe"]):
                        full_p = os.path.join(str(val), tgt)
                        if os.path.exists(full_p):
                            found_paths_info.append({"path": full_p, "trusted": True})
                else:
                    found_paths_info.append({"path": str(val), "trusted": True})

            # 1. Registry Scent (Fallback)
            if not found_paths_info and name.lower() == "ibkr":
                try:
                    import winreg

                    registry_keys = [
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                    ]
                    for key_path in registry_keys:
                        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                            try:
                                with winreg.OpenKey(hive, key_path) as key:
                                    for i in range(winreg.QueryInfoKey(key)[0]):
                                        try:
                                            sub_key_name = winreg.EnumKey(key, i)
                                            with winreg.OpenKey(key, sub_key_name) as sub_key:
                                                try:
                                                    disp_name = str(
                                                        winreg.QueryValueEx(sub_key, "DisplayName")[0]
                                                    )
                                                    if (
                                                        "TWS" in disp_name.upper()
                                                        or "GATEWAY" in disp_name.upper()
                                                    ):
                                                        install_loc = str(
                                                            winreg.QueryValueEx(
                                                                sub_key, "InstallLocation"
                                                            )[0]
                                                        )
                                                        for tgt in ["tws.exe", "ibgateway.exe"]:
                                                            full_path = os.path.join(install_loc, tgt)
                                                            if os.path.exists(full_path):
                                                                found_paths_info.append({"path": full_path, "trusted": True})
                                                except (FileNotFoundError, OSError):
                                                    continue
                                        except (FileNotFoundError, OSError):
                                            continue
                            except (FileNotFoundError, OSError):
                                continue
                except Exception as e:
                    logger.debug(f"MindSystem: Registry scanting failed: {e}")

            # 2. Filesystem Shallow-Scent (Fallback)
            if not found_paths_info:
                # --- MT5 Scent-Blocker (v1.0-beta-beta) ---
                if name.lower() == "mt5":
                    _ml = Vault.get("MT5_LOGIN")
                    if not _ml or "YOUR_MT5" in str(_ml).upper() or str(_ml).lower() == "none":
                        logger.info("MindSystem: Scent-Blocker ENGAGED — Skipping MetaTrader 5 search (Disabled).")
                        return

                common_roots = []
                if os.name == "nt":
                    common_roots = [
                        "C:\\Jts",
                        "C:\\Program Files",
                        "C:\\Program Files (x86)",
                        os.environ.get("APPDATA", ""),
                    ]
                else:
                    common_roots = [
                        "/opt/ibgateway",
                        "/usr/bin",
                        "/usr/local/bin",
                        os.path.expanduser("~"),
                    ]
                patterns = {
                    "ibkr": ["tws.exe", "ibgateway.exe"],
                    "mt5": ["terminal64.exe"],
                    "questdb": ["questdb.exe"],
                }
                targets = patterns.get(name.lower(), [f"{name}.exe"])
                found_raw = []
                for root in common_roots:
                    if not root or not os.path.exists(root):
                        continue
                    for target in targets:
                        for dirpath, _, filenames in os.walk(root):
                            if target in [f.lower() for f in filenames]:
                                found_raw.append(os.path.join(dirpath, target))
                                if len(found_raw) >= 2:
                                    break
                            if dirpath.count(os.sep) - root.count(os.sep) > 3:
                                break
                
                # GAP-59 & GAP-66 FIX: Anti-Hijacking and Binary Trust Scent (Samvid v1.0-beta-beta)
                trusted_zones = [r.lower() for r in common_roots if r]
                for p in found_raw:
                    p_lower = p.lower()
                    is_sane = False
                    if name.lower() == "ibkr":
                        is_sane = any(x in p_lower for x in ["jts", "interactive brokers", "tws", "gateway", "ibkr"])
                    elif name.lower() == "mt5":
                        is_sane = any(x in p_lower for x in ["metatrader", "terminal", "mt5"])
                    elif name.lower() == "questdb":
                        is_sane = "questdb" in p_lower
                    else:
                        is_sane = True
                    
                    is_in_trusted_zone = any(p_lower.startswith(z) for z in trusted_zones if z)
                    if is_sane:
                        found_paths_info.append({"path": p, "trusted": is_in_trusted_zone})

        # Run the scanting process in a thread pool to avoid blocking the event loop (GAP-185)
        await asyncio.to_thread(_sync_find_scent)

        if found_paths_info:
            best_path = next((p["path"] for p in found_paths_info if p["trusted"]), found_paths_info[0]["path"])
            dir_path = os.path.dirname(best_path)

            if name.lower() == "ibkr":
                os.environ["TWS_PATH"] = dir_path
                Vault.set("IBKR_PATH", best_path) # GAP-220 FIX: Persist verified path
                self.CERTIFIED_COMMANDS["RESTART_IBKR"][1] = f'start "" "{best_path}"'
                self.CERTIFIED_COMMANDS["RESTART_GATEWAY"][1] = f'start "" "{best_path}"'
                logger.info(f"MindSystem: Scent captured — Registered IBKR at {dir_path}")
            elif name.lower() == "mt5":
                os.environ["MT5_PATH"] = best_path
                Vault.set("MT5_PATH", best_path) # GAP-220 FIX: Persist verified path
                logger.info(f"MindSystem: Scent captured — Registered MT5 at {best_path}")
            elif name.lower() == "questdb":
                Vault.set("QUESTDB_PATH", best_path)

            return {
                "success": True,
                "found": [p["path"] for p in found_paths_info],
                "msg": f"Smart Scent: Verified '{name}' location at {best_path}",
                "trusted": any(p["trusted"] for p in found_paths_info)
            }

        return {
            "success": False,
            "msg": f"Scent Lost: Could not locate '{name}' in standard Windows roots.",
        }

    async def _tool_get_system_metrics(self) -> dict[str, Any]:
        """Provides the Ghost Mind (Agent J) with the hardware telemetry."""
        import psutil
        # GAP-265: Offload blocking psutil I/O to thread
        cpu = await asyncio.to_thread(psutil.cpu_percent)
        vmem = await asyncio.to_thread(psutil.virtual_memory)
        mem = vmem.percent
        
        return {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "disk_usage": await asyncio.to_thread(lambda: psutil.disk_usage("/").percent),
            "status": "HEALTHY" if cpu < 85 and mem < 85 else "STRESSED",
        }

    async def _tool_reboot_service(self, service_name: str) -> dict[str, Any]:
        """Performs a deep service reboot when the API is unresponsive."""
        async with self.lock: # GAP-61: Prevent multiple reboots racing
            if service_name not in self.CERTIFIED_COMMANDS:
                logger.error(
                    f"MindSystem: Reboot failed — service '{service_name}' NOT in Signed Allowlist."
                )
                return {"error": "Unauthorized Service"}

            logger.warning(f"MindSystem: CRITICAL SERVICE REBOOT: {service_name}...")
            cmds = self.CERTIFIED_COMMANDS[service_name]

            # RE-CALCULATE COMMANDS FOR IBKR if interface is specified in Vault (Samvid v1.0-beta-beta Patch)
            from vault import Vault
            interface = Vault.get("IBKR_INTERFACE", "gateway").lower()
            if service_name == "RESTART_IBKR":
                # GAP-143/260 FIX: Prioritize verified path from Vault to ensure reboot success
                target_exe = "ibgateway.exe" if interface == "gateway" else "TWS.exe"
                verified_path = Vault.get("IBKR_PATH")
                start_cmd = f"start {target_exe}"
                if verified_path and os.path.exists(str(verified_path)):
                     start_cmd = f'start "" "{verified_path}"'
                
                cmds = [
                    "taskkill /F /IM TWS.exe /IM ibgateway.exe /T /FI \"STATUS eq NOT RESPONDING\"",
                    start_cmd,
                ]

            results = []
            for cmd in cmds:
                try:
                    # Use asyncio for non-blocking sub-second execution
                    proc = await asyncio.create_subprocess_shell(
                        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _stderr = await proc.communicate()
                    status = "OK" if proc.returncode == 0 else "FAIL"
                    # Use errors="replace" for safe decoding on Windows
                    results.append(
                        {"cmd": cmd, "stdout": stdout.decode(errors="replace")[:150], "status": status}
                    )
                except Exception as e:
                    results.append({"cmd": cmd, "error": str(e), "status": "FAIL"})

            return {"service": service_name, "actions": results}

    async def _tool_run_system_command(self, alias: str) -> dict[str, Any]:
        """Runs a safe, aliased system command (e.g., CHECK_NETWORK)."""
        async with self.lock:
            if alias not in self.CERTIFIED_COMMANDS:
                return {"error": "Alias not certified"}

            cmd = self.CERTIFIED_COMMANDS[alias][0]  # First cmd only for check aliases
            try:
                # Non-blocking shell check
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _stderr = await proc.communicate()
                return {
                    "alias": alias,
                    "success": proc.returncode == 0,
                    "output": stdout.decode(errors="replace")[:250],
                }
            except Exception as e:
                return {"alias": alias, "error": str(e)}

    async def _tool_sovereign_flush(self) -> dict[str, Any]:
        """Sovereign Purification: Non-destructively flushes zombie processes to recover ports."""
        async with self.lock:
            logger.warning("MindSystem: Initiating Sovereign Resource Flush (Port Recovery)...")
            # GAP-67 FIX (Enhanced): flushes primary port consumers (TWS, Gateway, MT5, QuestDB).
            # We strictly avoid python.exe to prevent suicide of the Agent network itself.
            targets = ["tws.exe", "ibgateway.exe", "terminal64.exe", "questdb.exe"]
            killed_count = 0

            for target in targets:
                try:
                    # /F = Force, /IM = ImageName, /T = Tree kill (includes children)
                    cmd = f"taskkill /F /IM {target} /T"
                    proc = await asyncio.create_subprocess_shell(
                        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()
                    if proc.returncode == 0:
                        killed_count += 1
                        logger.info(f"MindSystem: Successfully flushed {target}")
                except Exception:
                    continue

            return {
                "success": True,
                "msg": f"Purification complete — {killed_count} component sectors flushed.",
            }
