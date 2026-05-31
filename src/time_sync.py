import asyncio
import logging
import os
import socket
import struct
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TimeSync:
    """
    Sovereign Time Synchronization Protocol.
    Synchronizes system clock with global NTP pool to prevent stale signal execution.
    """

    NTP_SERVERS = [
        "pool.ntp.org",
        "time.google.com",
        "time.nist.gov",
        "time.cloudflare.com",
        "time.windows.com",
    ]
    DNS_TIMEOUT_SEC = float(os.environ.get("SOVEREIGN_NTP_DNS_TIMEOUT_SEC", "1.5"))
    PROBE_TIMEOUT_SEC = float(os.environ.get("SOVEREIGN_NTP_PROBE_TIMEOUT_SEC", "2.0"))
    _offset = 0.0  # system_time + offset = ntp_time
    _is_periodic_running = False

    @classmethod
    async def sync(cls) -> bool:
        """Asynchronously determine the NTP offset."""
        results = await asyncio.gather(
            *(cls._query_ntp_server(server) for server in cls.NTP_SERVERS),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                continue
            server, offset = result
            cls._offset = offset
            logger.info("Clock synchronized with %s. Offset: %.4fs", server, offset)
            return True

        failed = sum(isinstance(result, BaseException) for result in results)
        logger.warning(
            "NTP UDP sync unavailable across %s/%s servers. Trying HTTP fallback.",
            failed,
            len(cls.NTP_SERVERS),
        )

        try:
            from session_manager import SovereignSession

            session = await SovereignSession.get_session()
            t0 = time.time()
            # Use a lightweight HEAD request to Cloudflare for minimal latency
            async with session.head("https://1.1.1.1", timeout=5) as resp:
                t1 = time.time()
                date_str = resp.headers.get("Date")
                if date_str:

                    def _parse_date(ds):
                        import email.utils

                        parsed_date = email.utils.parsedate_tz(ds)
                        if parsed_date:
                            return email.utils.mktime_tz(parsed_date)
                        return None

                    ntp_ts = await asyncio.to_thread(_parse_date, date_str)
                    if ntp_ts:
                        latency = (t1 - t0) / 2.0
                        # is at the start of the second. Adding 0.5s reduces mean error.
                        cls._offset = (ntp_ts + 0.5) - (t1 - latency)
                        logger.info(
                            f" Clock Synchronized via HTTP Fallback. Offset: {cls._offset:.4f}s (Latency Adj: {latency:.4f}s)"
                        )
                        return True
        except Exception as e:
            logger.warning(f"HTTP Time fallback failed: {e}")

        logger.error(" NTP Sync Failed across all protocols. Using local system clock (Risky).")
        return False

    @classmethod
    async def _query_ntp_server(cls, server: str) -> tuple[str, float]:
        """Resolve and probe one NTP server within a tight startup budget."""
        loop = asyncio.get_running_loop()
        addr_info = await asyncio.wait_for(
            loop.getaddrinfo(
                server,
                123,
                family=socket.AF_INET,
                type=socket.SOCK_DGRAM,
                proto=socket.IPPROTO_UDP,
            ),
            timeout=cls.DNS_TIMEOUT_SEC,
        )
        if not addr_info:
            raise OSError(f"no IPv4 UDP address for {server}")
        ip_addr = addr_info[0][4][0]
        offset = await asyncio.wait_for(
            cls._get_ntp_offset(ip_addr, timeout_sec=cls.PROBE_TIMEOUT_SEC),
            timeout=cls.PROBE_TIMEOUT_SEC + 0.25,
        )
        return server, offset

    @classmethod
    async def start_periodic_sync(cls, interval_hours: int = 6):
        """Background task that periodically re-syncs the clock to prevent drift in long sessions."""
        if cls._is_periodic_running:
            return
        cls._is_periodic_running = True
        logger.info(f"TimeSync: Background drift correction active (Interval: {interval_hours}h).")

        while cls._is_periodic_running:
            await asyncio.sleep(interval_hours * 3600)
            await cls.sync()

    @staticmethod
    async def _get_ntp_offset(host: str, *, timeout_sec: float = 2.0) -> float:
        """Standard NTP UDP request (RFC 5905)."""
        # NTP packet is 48 bytes.
        # First byte is 0x1B (LI=0, VN=3, Mode=3 client)
        packet = bytearray(48)
        packet[0] = 0x1B

        # Use a thread since socket.sendto/recvfrom are blocking
        loop = asyncio.get_event_loop()

        def _exchange():
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout_sec)
                # Send request
                send_time = time.time()
                s.sendto(packet, (host, 123))
                # Receive response
                data, _ = s.recvfrom(48)
                recv_time = time.time()
                if len(data) < 48:
                    raise ValueError(f"short NTP packet from {host}: {len(data)} bytes")

                # Extract transmit timestamp (bytes 40-48)
                # Format is 32-bit seconds since 1900, 32-bit fraction
                unpacked = struct.unpack("!12I", data)
                ntp_seconds = unpacked[10] - 2208988800  # Convert to Unix epoch
                ntp_fraction = unpacked[11] / (2**32)
                ntp_time = ntp_seconds + ntp_fraction

                # Round trip delay calculation (simplified)
                # t0 = send_time, t3 = recv_time, t2 = ntp_time
                # offset = ((t1-t0) + (t2-t3)) / 2
                # Assuming symmetric network delay: ntp_time - (send+recv)/2
                return ntp_time - ((send_time + recv_time) / 2)

        return await loop.run_in_executor(None, _exchange)

    @classmethod
    def now(cls) -> datetime:
        """Returns the synchronized datetime."""
        synchronized_ts = time.time() + cls._offset
        return datetime.fromtimestamp(synchronized_ts, tz=timezone.utc)

    @classmethod
    def get_offset(cls) -> float:
        return cls._offset
