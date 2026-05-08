CC=gcc
CFLAGS=-O3 -march=native -mtune=native -flto -ffast-math

all:
	$(CC) $(CFLAGS) -shared -o build/libsovereign.so src/heartbeat.c src/time_sync.c src/memory_guard.c
