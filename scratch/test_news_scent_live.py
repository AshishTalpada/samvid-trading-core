import asyncio
import os
import json
import re
import websockets
import logging
import time
from datetime import datetime

# Setup minimal logging to see the scent
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TV_SCENT_PROBE - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TVNewsScentProbe:
    def __init__(self) -> None:
        self.url = "wss://data.tradingview.com/socket.io/websocket"
        self.session_id = f"ns_{os.urandom(6).hex()}"

    def _format_message(self, data: dict) -> str:
        msg = json.dumps(data, separators=(",", ":"))
        return f"~m~{len(msg)}~m~{msg}"

    def _parse_messages(self, raw_data: str) -> list[dict]:
        results = []
        parts = re.split(r"~m~\d+~m~", raw_data)
        for p in parts:
            if p and p.startswith("{"):
                try:
                    results.append(json.loads(p))
                except Exception:
                    continue
        return results

    async def run(self) -> None:
        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        logger.info(f"Connecting to {self.url}...")
        try:
            async with websockets.connect(self.url, additional_headers=headers) as ws:
                # 0. Set Auth Token (Necessary for some session types)
                await ws.send(self._format_message({"m": "set_auth_token", "p": ["unauthorized_user_token"]}))
                
                # 1. Init News Session
                # Note: Some sources say 'news_create_session', others say 'news_session'
                method = "news_create_session"
                await ws.send(self._format_message({"m": method, "p": [self.session_id]}))
                
                # 2. Setup News Feed (instead of 'news_feed' command)
                await ws.send(self._format_message({
                    "m": "news_setup", 
                    "p": [
                        self.session_id, 
                        "news_scent_feed", 
                        {"provider": "tradingview", "category": "all", "symbol": ""}
                    ]
                }))
                
                logger.info("✓ PROBE: Neural Handshake Sent. Waiting for response...")

                async for message in ws:
                    if message.startswith("~h~"):
                        await ws.send(message)
                        continue
                        
                    msgs = self._parse_messages(message)
                    for msg in msgs:
                        m_type = msg.get("m")
                        if m_type:
                            logger.info(f"Incoming TV message type: {m_type}")
                        
                        if m_type == "news_item":
                            p = msg.get("p", [])
                            if len(p) > 2 and isinstance(p[2], dict):
                                item = p[2]
                                headline = item.get("title", item.get("headline", ""))
                                source = item.get("source", "UNKNOWN")
                                print(f"\n[LIVE NEWS] {datetime.now().strftime('%H:%M:%S')} | {source} | {headline}")
                        elif m_type == "critical_error":
                            logger.error(f"TV CRITICAL ERROR: {msg}")
                            # Try fallback method if invalid_method
                            if "invalid_method" in str(msg):
                                logger.warning("Switching to fallback method: 'news_session'...")
                                await ws.send(self._format_message({"m": "news_session", "p": [self.session_id]}))
                                # Redo setup
                                await ws.send(self._format_message({
                                    "m": "news_setup", 
                                    "p": [self.session_id, "news_scent_feed", {"provider": "tradingview", "category": "all", "symbol": ""}]
                                }))

        except Exception as e:
            logger.error(f"Scent Probe Failed: {e}")

if __name__ == "__main__":
    probe = TVNewsScentProbe()
    try:
        asyncio.run(probe.run())
    except KeyboardInterrupt:
        pass
