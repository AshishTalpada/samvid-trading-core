CC=gcc
CXX=g++
CPPFLAGS=-Isrc
CFLAGS=-O3 -march=native -mtune=native -flto -ffast-math -fPIC -std=c11
CXXFLAGS=-O3 -march=native -mtune=native -flto -ffast-math -fPIC -std=c++17

# Detect OS
ifeq ($(OS),Windows_NT)
    EXT=.dll
    MKDIR_P=powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path"
else
    EXT=.so
    MKDIR_P=mkdir -p
endif

TARGET=build/libsovereign$(EXT)

SOURCES_C=src/heartbeat.c quarantine/time_sync.c src/memory_guard.c src/hardware_audit.c src/safety_core.c
SOURCES_CPP=src/chaos_metrics.cpp src/agent_a_simd.cpp quarantine/rng_audit.cpp
OBJECTS=$(patsubst %.c,build/%.o,$(SOURCES_C)) $(patsubst %.cpp,build/%.o,$(SOURCES_CPP))

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(MKDIR_P) $(dir $@)
	$(CXX) $(CXXFLAGS) -shared -o $@ $(OBJECTS)

build/%.o: %.c
	$(MKDIR_P) $(dir $@)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c -o $@ $<

build/%.o: %.cpp
	$(MKDIR_P) $(dir $@)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -rf build
