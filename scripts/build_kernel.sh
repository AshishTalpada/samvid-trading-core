#!/bin/bash
# Apply PREEMPT_RT patch and disable tickless idle
make menuconfig
# CONFIG_PREEMPT_RT=y
# CONFIG_NO_HZ_FULL=y
make -j$(nproc)
make modules_install install
