#!/bin/bash
# Sovereign Network Topology Auto-Repair
# Detection and failover for ultra-low latency dark fiber paths.

INTERFACE_PRIMARY="eth0"
INTERFACE_SECONDARY="eth1"
GATEWAY_PRIMARY="10.0.0.1"
GATEWAY_SECONDARY="10.0.0.2"

echo "[NET_REPAIR] Monitoring $INTERFACE_PRIMARY link status..."

# 1. Check if the primary link is physically up
if ! ip link show $INTERFACE_PRIMARY | grep -q "state UP"; then
    echo "[CRITICAL] $INTERFACE_PRIMARY is DOWN. Rerouting topology to secondary satellite link..."
    ip route replace default via $GATEWAY_SECONDARY dev $INTERFACE_SECONDARY
    exit 1
fi

# 2. Check for carrier signal
CARRIER=$(cat /sys/class/net/$INTERFACE_PRIMARY/carrier 2>/dev/null || echo "0")
if [ "$CARRIER" -ne "1" ]; then
    echo "[CRITICAL] No carrier on $INTERFACE_PRIMARY. Flipping to backup link..."
    ip route replace default via $GATEWAY_SECONDARY dev $INTERFACE_SECONDARY
    exit 1
fi

# 3. Check for packet loss on the primary gateway
if ! ping -c 1 -W 1 $GATEWAY_PRIMARY > /dev/null; then
    echo "[WARNING] Gateway $GATEWAY_PRIMARY unreachable. Attempting soft repair..."
    ip route flush cache
    ip route replace default via $GATEWAY_SECONDARY dev $INTERFACE_SECONDARY
    echo "[SUCCESS] Rerouting topology complete."
else
    echo "[SUCCESS] Primary network path is healthy."
fi
