#include <stdio.h>

extern "C" void encrypt_stream(char* buffer, int len) {
    // Pre-Disk Encryption: Logs encrypted BEFORE being written to disk
    // Stub implementation
    for(int i=0; i<len; i++) {
        buffer[i] ^= 0xAA;
    }
}
