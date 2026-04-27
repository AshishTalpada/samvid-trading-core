    async def connect_ibkr(self) -> bool | None:
        """Connect to Interactive Brokers TWS/Gateway (Sovereign Parallel Probe V9.99)"""
        logger.info(f"Connecting to IBKR at {self.ibkr_host}:{self.ibkr_port}...")

        try:
            from ib_insync import IB, IBC, util  # pyre-ignore[21]

            self.ibkr_client = IB()

            # Step 1: Auto-launch IB Gateway/TWS via IBC if configured
            ibc_path = os.environ.get("IBC_PATH") or Vault.get("IBC_PATH")

            # SETO V8.0 SHIELD: Skip IBC if software already active (prevents Windows popups)
            if await self._is_ibkr_process_active():
                logger.info(
                    "✓ IBKR software already active — diverting connection (Bypassing IBC)."
                )
                ibc_path = None

            tws_path = os.environ.get("TWS_PATH") or Vault.get("TWS_PATH", "C:\\Jts")
            ibkr_user = Vault.get("IBKR_PAPER_USERNAME")
            ibkr_pass = Vault.get("IBKR_PAPER_PASSWORD")

            if ibc_path and ibkr_user and ibkr_pass:
                logger.info("Starting IBC auto-login for paper trading...")

                # Auto-detect TWS/Gateway version folder
                tws_version = 985
                try:
                    # SEEDS: Support both TWS and IBGateway directory hierarchies
                    roots_to_check = [tws_path]
                    if os.path.exists(os.path.join(tws_path, "ibgateway")):
                        roots_to_check.append(os.path.join(tws_path, "ibgateway"))
                    if os.path.exists(os.path.join(tws_path, "tws")):
                        roots_to_check.append(os.path.join(tws_path, "tws"))

                    folders = []
                    for root in roots_to_check:
                        _f = [int(f) for f in os.listdir(root) if f.isdigit()]
                        folders.extend(_f)

                    if folders:
                        tws_version = max(folders)
                        logger.info(f"Auto-detected TWS version: {tws_version}")
                except Exception as e:
                    logger.debug(f"Could not auto-detect TWS version: {e}")

                # SETO V8.0: Interface Preference (gateway vs tws)
                ibkr_interface = Vault.get("IBKR_INTERFACE", "gateway").lower()

                # SETO V8.0 Path Injection: If gateway mode, ensure twsPath points to the ibgateway root
                effective_tws_path = tws_path
                if ibkr_interface == "gateway" and os.path.exists(os.path.join(tws_path, "ibgateway")):
                    effective_tws_path = os.path.join(tws_path, "ibgateway")

                self.ibc = IBC(
                    twsVersion=tws_version,
                    gateway=(ibkr_interface == "gateway"),
                    tradingMode="paper",
                    userid=ibkr_user,
                    password=ibkr_pass,
                    twsPath=effective_tws_path,
                    ibcPath=ibc_path,
                )
                ibc = self.ibc
                if ibc:
                    ibc.start()
                logger.info("Waiting 45 seconds for TWS/Gateway to initialize (SETO V8.0 Extended Wait)...")
                await asyncio.sleep(45)

            # Try configured port first, then alternative port
            ports_to_try = [self.ibkr_port]
            alt_port = 4002 if self.ibkr_port == 7497 else 7497
            ports_to_try.append(alt_port)

            connected = False
            base_client_id = self.ibkr_client_id

            # Use faster discovery if account is pre-configured in Vault/.env
            pre_configured_account = Vault.get("IBKR_ACCOUNT_ID")

            client = self.ibkr_client
            if not client:
                raise ConnectionError("IBKR client not initialized")

            # Sovereign Brute-Force Handshake (Triple Protocol Probe)
            for client_id_offset in range(50):
                current_id = base_client_id + client_id_offset
                for host in ["localhost", "127.0.0.1", "::1"]:
                    for port in ports_to_try:
                        try:
                            # Log primary attempts only to keep terminal clean
                            if (port == self.ibkr_port and host == "localhost"):
                                logger.info(f"Sovereign Handshake Probe: {host}:{port} (ID: {current_id})...")
                            else:
                                logger.debug(f"Background Probe: {host}:{port} (ID: {current_id})...")

                            try:
                                await asyncio.wait_for(
                                    client.connectAsync(host=host, port=port, clientId=current_id, readonly=False),
                                    timeout=15.0,  # Sovereign Parallel Wait
                                )
                            except Exception as e:
                                if (
                                    "321" in str(e) or "Group name" in str(e)
                                ) and not pre_configured_account:
                                    logger.warning("FA account detected. Auto-discovering sub-account ID...")
                                    accounts = client.managedAccounts()
                                    target_account = accounts[0] if accounts else "DUP511167"

                                    client.disconnect()
                                    await asyncio.sleep(1)
                                    self.ibkr_client = client = IB()
                                    await asyncio.wait_for(
                                        client.connectAsync(host=host, port=port, clientId=current_id, account=target_account),
                                        timeout=15.0,
                                    )
                                else:
                                    raise

                            if client.isConnected():  # pyre-ignore[16]
                                connected = True
                                self.ibkr_client_id = current_id
                                break
                        except Exception as e:
                            logger.debug(f"Connection attempt failed on primary port {port}: {e}")
                            try:
                                client.disconnect()  # pyre-ignore[16]
                            except Exception:
                                pass
                            self.ibkr_client = client = IB()
                            continue
                    if connected:
                        break
                if connected:
                    break

            if not connected:
                logger.error(f"IBKR connection failed on ports {ports_to_try} after triple-probe sweep.")
                return False

            accounts = client.managedAccounts()
            logger.info(f"✓ IBKR connected - Accounts: {accounts}")

            # ━€━€ TCP NoDelay: Disable Nagle's Algorithm for minimum order latency ━€━€
            try:
                if hasattr(client.client, "conn") and client.client.conn.socket is not None:
                    raw_sock = client.client.conn.socket
                    raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    logger.info("✅ TCP_NODELAY enabled on IBKR socket (Nagle's Algorithm disabled)")
                elif hasattr(client.client, "socket") and client.client.socket is not None:
                    raw_sock = client.client.socket
                    raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    logger.info("✅ TCP_NODELAY enabled on IBKR socket (Legacy path)")
            except Exception as _tcp_err:
                logger.debug(f"TCP_NODELAY not applied (non-critical): {_tcp_err}")

            # Explicitly set the wrapper's account if available to avoid FA group errors
            if accounts:
                client.wrapper.accounts = accounts
                logger.info(f"Using account: {accounts[0]}")

            # Store connection info in database
            db = self.db_conn
            if db:
                cursor = db.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("ibkr_status", "connected"),
                )
                cursor.close()

            return True

        except Exception as e:
            logger.error(f"IBKR connection error: {e}")
            return False
