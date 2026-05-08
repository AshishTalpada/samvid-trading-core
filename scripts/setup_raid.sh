#!/bin/bash
# NVMe RAID 0 Array Setup
mdadm --create --verbose /dev/md0 --level=0 --raid-devices=4 /dev/nvme0n1 /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1
mkfs.xfs /dev/md0
