#!/bin/bash
# Isolate cores 2-8 for trading system
cset shield -c 2-8 -k on
cset shield --exec -- python3 src/main.py
