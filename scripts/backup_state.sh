#!/bin/bash
# Save entire Brain state to offline vault nightly
tar -czf /mnt/offline_vault/brain_state_$(date +%F).tar.gz /data/brain_state/
