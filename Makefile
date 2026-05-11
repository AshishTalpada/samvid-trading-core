CC=gcc
CXX=g++
CFLAGS=-O3 -march=native -mtune=native -flto -ffast-math -fPIC
CXXFLAGS=$(CFLAGS) -std=c++17

# Detect OS
ifeq ($(OS),Windows_NT)
    EXT=.dll
    MKDIR=if not exist build mkdir build
else
    EXT=.so
    MKDIR=mkdir -p build
endif

TARGET=build/libsovereign$(EXT)

SOURCES_C=src/heartbeat.c src/time_sync.c src/memory_guard.c src/hardware_audit.c src/safety_core.c
SOURCES_CPP=src/chaos_metrics.cpp src/agent_a_simd.cpp src/rng_audit.cpp

all: $(TARGET)

$(TARGET): $(SOURCES_C) $(SOURCES_CPP)
	$(MKDIR)
	$(CXX) $(CXXFLAGS) -shared -o $@ $(SOURCES_C) $(SOURCES_CPP)

clean:
	rm -rf build
