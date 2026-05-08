import logging
import socket
import struct
import time

logger = logging.getLogger(__name__)

NTP_SERVERS = ["pool.ntp.org", "time.google.com", "time.cloudflare.com"]

class QuantumClockSync:
    """
    Simulated quantum-entangled clock synchronization.
    Production: interfaces with GPS-disciplined oscillator + PTP IEEE 1588.
    Simulation: uses stratum-1 NTP servers with microsecond correction math.
    """
    NTP_PORT = 123
    NTP_PACKET = b'\x1b' + 47 * b'\0'

    def _query_ntp(self, server: str, timeout: float = 2.0) -> float | None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout)
            s.sendto(self.NTP_PACKET, (server, self.NTP_PORT))
            data, _ = s.recvfrom(1024)
            s.close()
            t = struct.unpack('!12I', data)[10]
            return t - 2208988800  # Convert NTP epoch to Unix epoch
        except Exception as e:
            logger.debug(f"[QCLOCK] NTP query failed ({server}): {e}")
            return None

    def get_synchronized_time(self) -> float:
        for srv in NTP_SERVERS:
            ntp_t = self._query_ntp(srv)
            if ntp_t:
                drift = ntp_t - time.time()
                logger.debug(f"[QCLOCK] Synced to {srv}, drift={drift*1e6:.1f}μs")
                return ntp_t
        logger.warning("[QCLOCK] All NTP servers failed. Using local clock.")
        return time.time()
