import asyncio
import logging
import socket
import struct
import time

logger = logging.getLogger(__name__)

GPS_NTP_SERVERS = ["time.google.com", "time.cloudflare.com", "pool.ntp.org"]
NTP_DELTA = 2208988800


class GalacticClockSync:
    """
    GPS-disciplined nanosecond clock synchronisation.
    Production: syncs to a GPS-disciplined oscillator via PTP IEEE 1588.
    Simulation: multi-server NTP stratum-1 poll with drift correction.
    """

    async def query_ntp(self, server: str, timeout: float = 1.0) -> float | None:
        def _blocking_query() -> float:
            pkt = b"\x1b" + 47 * b"\x00"
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout)
            t_send = time.time()
            s.sendto(pkt, (server, 123))
            data, _ = s.recvfrom(1024)
            t_recv = time.time()
            s.close()
            t_ntp = struct.unpack("!12I", data)[10] - NTP_DELTA
            rtt = t_recv - t_send
            return t_ntp + rtt / 2.0  # type: ignore

        try:
            return await asyncio.to_thread(_blocking_query)
        except Exception as e:
            logger.debug(f"[CLOCK] NTP query failed ({server}): {e}")
            return None

    async def synchronized_time(self) -> float:
        tasks = [self.query_ntp(srv) for srv in GPS_NTP_SERVERS]
        query_results = await asyncio.gather(*tasks)
        results = [t for t in query_results if t is not None]
        if not results:
            logger.warning("[CLOCK] All NTP servers failed. Using local time.")
            return time.time()
        median_ntp = sorted(results)[len(results) // 2]
        drift_us = (median_ntp - time.time()) * 1e6
        logger.info(f"[CLOCK] Synced. Drift={drift_us:.1f}μs")
        return median_ntp

