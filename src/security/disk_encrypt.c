#include <wmmintrin.h> // AES-NI instructions
#include <immintrin.h>
#include <stdint.h>

/**
 * Hardware AES-NI Disk Encryption Core
 * Implements high-throughput AES-128 block encryption with hardware acceleration.
 * This is the foundation for the zero-latency encrypted logging system.
 */

// Key Expansion Macro
#define AES_128_KEY_EXPAND(key, rcon) \
    _mm_aeskeygenassist_si128(key, rcon)

static inline __m128i aes_128_key_expansion_assist(__m128i temp1, __m128i temp2) {
    __m128i temp3;
    temp2 = _mm_shuffle_epi32(temp2, 0xff);
    temp3 = _mm_slli_si128(temp1, 0x4);
    temp1 = _mm_xor_si128(temp1, temp3);
    temp3 = _mm_slli_si128(temp3, 0x4);
    temp1 = _mm_xor_si128(temp1, temp3);
    temp3 = _mm_slli_si128(temp3, 0x4);
    temp1 = _mm_xor_si128(temp1, temp3);
    temp1 = _mm_xor_si128(temp1, temp2);
    return temp1;
}

/// Expands a 128-bit raw key into the 11 round keys required for AES-128
extern "C" void aes_128_key_expand(const uint8_t* user_key, __m128i* key_schedule) {
    key_schedule[0] = _mm_loadu_si128((const __m128i*)user_key);
    
    __m128i temp = AES_128_KEY_EXPAND(key_schedule[0], 0x01);
    key_schedule[1] = aes_128_key_expansion_assist(key_schedule[0], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[1], 0x02);
    key_schedule[2] = aes_128_key_expansion_assist(key_schedule[1], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[2], 0x04);
    key_schedule[3] = aes_128_key_expansion_assist(key_schedule[2], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[3], 0x08);
    key_schedule[4] = aes_128_key_expansion_assist(key_schedule[3], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[4], 0x10);
    key_schedule[5] = aes_128_key_expansion_assist(key_schedule[4], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[5], 0x20);
    key_schedule[6] = aes_128_key_expansion_assist(key_schedule[5], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[6], 0x40);
    key_schedule[7] = aes_128_key_expansion_assist(key_schedule[6], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[7], 0x80);
    key_schedule[8] = aes_128_key_expansion_assist(key_schedule[7], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[8], 0x1B);
    key_schedule[9] = aes_128_key_expansion_assist(key_schedule[8], temp);
    temp = AES_128_KEY_EXPAND(key_schedule[9], 0x36);
    key_schedule[10] = aes_128_key_expansion_assist(key_schedule[9], temp);
}

/// Encrypts a single 128-bit block using AES-NI
extern "C" void aes_ni_encrypt_block(const __m128i* plaintext, const __m128i* key_schedule, __m128i* ciphertext) {
    __m128i m = _mm_xor_si128(*plaintext, key_schedule[0]);
    m = _mm_aesenc_si128(m, key_schedule[1]);
    m = _mm_aesenc_si128(m, key_schedule[2]);
    m = _mm_aesenc_si128(m, key_schedule[3]);
    m = _mm_aesenc_si128(m, key_schedule[4]);
    m = _mm_aesenc_si128(m, key_schedule[5]);
    m = _mm_aesenc_si128(m, key_schedule[6]);
    m = _mm_aesenc_si128(m, key_schedule[7]);
    m = _mm_aesenc_si128(m, key_schedule[8]);
    m = _mm_aesenc_si128(m, key_schedule[9]);
    *ciphertext = _mm_aesenclast_si128(m, key_schedule[10]);
}

/// Bulk encryption for logging stream (Electronic Codebook mode for simple blocks)
extern "C" void aes_ni_encrypt_buffer(uint8_t* data, uint32_t len, const __m128i* key_schedule) {
    for (uint32_t i = 0; i < len; i += 16) {
        __m128i block = _mm_loadu_si128((const __m128i*)(data + i));
        aes_ni_encrypt_block(&block, key_schedule, &block);
        _mm_storeu_si128((__m128i*)(data + i), block);
    }
}
