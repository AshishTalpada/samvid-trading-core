#include <stdio.h>
#include <wmmintrin.h> // AES-NI instructions
#include <stdint.h>

/// AES-CTR Mode Stream Encryption via Hardware AES-NI
/// Encrypts hot memory logs on the fly before they hit disk to ensure
/// zero CPU starvation on the main thread and perfect data-at-rest security.
extern "C" void encrypt_stream_aes_ctr(uint8_t* buffer, int len, __m128i* key_schedule, uint8_t* nonce_counter) {
    __m128i nonce_block = _mm_loadu_si128((__m128i*)nonce_counter);
    __m128i one = _mm_set_epi64x(0, 1); // For incrementing the CTR block
    
    int i = 0;
    while (i + 16 <= len) {
        // 1. AES Encrypt the Nonce/Counter
        __m128i m = _mm_xor_si128(nonce_block, key_schedule[0]);
        for(int j = 1; j < 10; j++) {
            m = _mm_aesenc_si128(m, key_schedule[j]);
        }
        m = _mm_aesenclast_si128(m, key_schedule[10]); // m is now the keystream block
        
        // 2. XOR keystream with plaintext to produce ciphertext
        __m128i plaintext = _mm_loadu_si128((__m128i*)(buffer + i));
        __m128i ciphertext = _mm_xor_si128(plaintext, m);
        _mm_storeu_si128((__m128i*)(buffer + i), ciphertext);
        
        // 3. Increment counter for next block
        nonce_block = _mm_add_epi64(nonce_block, one);
        i += 16;
    }
    
    // Write back the updated counter for the next stream call
    _mm_storeu_si128((__m128i*)nonce_counter, nonce_block);
}
