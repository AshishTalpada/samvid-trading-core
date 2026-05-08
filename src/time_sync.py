import logging
import socket
import struct
import time

logger = logging.getLogger(__name__)

class PrecisionTimeSyncer:
    """
    Sub-millisecond Network Time Protocol (NTP) Synchronizer.
    HFT operations require microsecond alignment between the local CPU clock
    and exchange matching engines to prevent false arbitrage triggers.
    """
    NTP_SERVER = "time.nist.gov"
    TIME1970 = 2208988800 # 1970-01-01 00:00:00

    def __init__(self):
        self.clock_offset_ms = 0.0

    def synchronize(self) -> bool:
        """
        Queries an authoritative atomic clock server via UDP.
        Calculates the round-trip latency to determine the exact clock offset.
        """
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(2.0)

        # NTP packet format: 48 bytes. First byte 0x1B = Client mode, Version 3
        data = b'\x1b' + 47 * b'\0'

        try:
            t1 = time.time()
            client.sendto(data, (self.NTP_SERVER, 123))
            msg, _ = client.recvfrom(1024)
            t4 = time.time()

            # Unpack the 64-bit Transmit Timestamp (seconds and fraction)
            s, f = struct.unpack('!12I', msg)[10:12]

            # Convert fraction to seconds
            ntp_time = s - self.TIME1970 + (f / 2**32)

            # The round trip time (RTT)
            rtt = t4 - t1

            # The local time when the packet was processed by the server
            local_time_at_server_tx = t4 - (rtt / 2.0)

            # Clock offset: Positive means our clock is BEHIND the server
            self.clock_offset_ms = (ntp_time - local_time_at_server_tx) * 1000.0

            logger.info(f"[TIME SYNC] Synced with {self.NTP_SERVER}. RTT: {rtt*1000:.2f}ms. Clock Offset: {self.clock_offset_ms:.3f}ms")
            return True

        except Exception as e:
            logger.error(f"[TIME SYNC] NTP Synchronization failed: {e}")
            return False
        finally:
            client.close()

    def get_synced_time_ms(self) -> float:
        """Returns the current timestamp in milliseconds, corrected by the atomic clock offset."""
        return (time.time() * 1000.0) + self.clock_offset_ms
