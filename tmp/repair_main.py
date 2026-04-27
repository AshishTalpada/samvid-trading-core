import os

path = 'src/main.py'
with open(path, 'r') as f:
    lines = f.readlines()

start = -1
end = -1
for i, line in enumerate(lines):
    if 'async def connect_ibkr' in line:
        start = i
    if start != -1 and 'async def connect_mt5' in line:
        end = i
        break

if start != -1 and end != -1:
    new_method = [
        '    async def connect_ibkr(self) -> bool | None:\n',
        '        \"\"\"Connect to Interactive Brokers TWS/Gateway (Sovereign Serialized Probe V9.99)\"\"\"\n',
        '        if not hasattr(self, \"_ibkr_lock\"):\n',
        '            self._ibkr_lock = asyncio.Lock()\n',
        '\n',
        '        async with self._ibkr_lock:\n',
        '            logger.info(\"Connecting to IBKR (Serialized Matrix Probing)...\")\n',
        '            try:\n',
        '                from ib_insync import IB, IBC, util  # pyre-ignore[21]\n',
        '                self.ibkr_client = IB()\n',
        '\n',
        '                # Step 1: Auto-launch IB Gateway/TWS via IBC if configured\n',
        '                ibc_path = os.environ.get(\"IBC_PATH\") or Vault.get(\"IBC_PATH\")\n',
        '                if await self._is_ibkr_process_active():\n',
        '                    logger.info(\"✓ IBKR software active (Bypassing IBC).\")\n',
        '                    ibc_path = None\n',
        '\n',
        '                tws_path = os.environ.get(\"TWS_PATH\") or Vault.get(\"TWS_PATH\", \"C:\\\\Jts\")\n',
        '                ibkr_user = Vault.get(\"IBKR_PAPER_USERNAME\")\n',
        '                ibkr_pass = Vault.get(\"IBKR_PAPER_PASSWORD\")\n',
        '\n',
        '                if ibc_path and ibkr_user and ibkr_pass: \n',
        '                    logger.info(\"Starting IBC auto-login for paper trading...\")\n',
        '                    tws_version = 985\n',
        '                    try:\n',
        '                        roots_to_check = [tws_path]\n',
        '                        if os.path.exists(os.path.join(tws_path, \"ibgateway\")):\n',
        '                            roots_to_check.append(os.path.join(tws_path, \"ibgateway\"))\n',
        '                        if os.path.exists(os.path.join(tws_path, \"tws\")):\n',
        '                            roots_to_check.append(os.path.join(tws_path, \"tws\"))\n',
        '                        folders = [int(f) for root in roots_to_check if os.path.exists(root) for f in os.listdir(root) if f.isdigit()]\n',
        '                        if folders: tws_version = max(folders)\n',
        '                    except Exception: pass\n',
        '\n',
        '                    ibkr_interface = Vault.get(\"IBKR_INTERFACE\", \"gateway\").lower()\n',
        '                    effective_tws_path = tws_path\n',
        '                    if ibkr_interface == \"gateway\" and os.path.exists(os.path.join(tws_path, \"ibgateway\")):\n',
        '                        effective_tws_path = os.path.join(tws_path, \"ibgateway\")\n',
        '\n',
        '                    self.ibc = IBC(twsVersion=tws_version, gateway=(ibkr_interface == \"gateway\"), tradingMode=\"paper\", userid=ibkr_user, password=ibkr_pass, twsPath=effective_tws_path, ibcPath=ibc_path)\n',
        '                    if self.ibc: self.ibc.start()\n',
        '                    logger.info(\"Waiting 45 seconds for TWS/Gateway to initialize...\")\n',
        '                    await asyncio.sleep(45)\n',
        '\n',
        '                ports_to_try = [self.ibkr_port, 4002 if self.ibkr_port == 7497 else 7497]\n',
        '                connected = False\n',
        '                base_client_id = self.ibkr_client_id\n',
        '                pre_configured_account = Vault.get(\"IBKR_ACCOUNT_ID\")\n',
        '                client = self.ibkr_client\n',
        '\n',
        '                for client_id_offset in range(50):\n',
        '                    current_id = base_client_id + client_id_offset\n',
        '                    for host in [\"::1\", \"localhost\", \"127.0.0.1\"]:\n',
        '                        for port in ports_to_try:\n',
        '                            try:\n',
        '                                if host == \"::1\" and port == self.ibkr_port:\n',
        '                                    logger.info(f\"Sovereign Probe: {host}:{port} (ID: {current_id})...\")\n',
        '                                await asyncio.wait_for(client.connectAsync(host=host, port=port, clientId=current_id, readonly=False), timeout=30.0)\n',
        '                                if client.isConnected():\n',
        '                                    connected = True\n',
        '                                    self.ibkr_client_id = current_id\n',
        '                                    break\n',
        '                            except Exception:\n',
        '                                try: client.disconnect()\n',
        '                                except Exception: pass\n',
        '                                self.ibkr_client = client = IB()\n',
        '                                continue\n',
        '                        if connected: break\n',
        '                    if connected: break\n',
        '\n',
        '                if not connected: return False\n',
        '                accounts = client.managedAccounts()\n',
        '                logger.info(f\"✓ IBKR connected - Accounts: {accounts}\")\n',
        '                if accounts:\n',
        '                    client.wrapper.accounts = accounts\n',
        '                    logger.info(f\"Using account: {accounts[0]}\")\n',
        '                return True\n',
        '\n',
        '            except Exception as e:\n',
        '                logger.error(f\"IBKR connection error: {e}\")\n',
        '                return False\n'
    ]
    
    lines[start:end] = new_method
    with open(path, 'w') as f:
        f.writelines(lines)
    print('SUCCESS: Structural Overwrite Applied')
else:
    print('ERROR: Bounds not found')
