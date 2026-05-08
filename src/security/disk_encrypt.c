#include <stdio.h>
#include <wmmintrin.h> // AES-NI instructions

// Deep Dive: Hardware AES-NI disk encryption
// Zero-CPU overhead logging by pushing encryption to the hardware AES accelerator
extern "C" void aes_ni_encrypt_block(__m128i* plaintext, __m128i* key_schedule, __m128i* ciphertext) {
    __m128i m = *plaintext;
    m = _mm_xor_si128(m, key_schedule[0]);
    for(int i=1; i<10; i++){
        m = _mm_aesenc_si128(m, key_schedule[i]);
    }
    *ciphertext = _mm_aesenclast_si128(m, key_schedule[10]);
}
