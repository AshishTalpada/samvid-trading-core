// =========================================================================
// DEPRECATION WARNING: Phase 2 De-bloat
// Custom cryptography (especially toy PQC implementations) should not be
// used in production systems. This is now disabled by default.
// Use standard TLS/AES for data-in-transit or data-at-rest.
// =========================================================================
#![cfg(feature = "experimental_crypto")]

use rand::{thread_rng, Rng};

// Experimental post-quantum lattice cryptography (module learning with errors).
// This toy implementation is compiled only for research and must not protect production data.
// Parameters for a toy-Kyber implementation
const N: usize = 256; // Polynomial degree
const Q: i32 = 3329; // Prime modulus
const K: usize = 2; // Module dimension

#[derive(Clone)]
pub struct Poly {
    pub coeffs: [i32; N],
}

impl Default for Poly {
    fn default() -> Self {
        Self::new()
    }
}

impl Poly {
    pub fn new() -> Self {
        Poly { coeffs: [0; N] }
    }

    /// Add two polynomials in the ring Z_q[X]/(X^N + 1)
    pub fn add(&self, other: &Poly) -> Poly {
        let mut result = Poly::new();
        for i in 0..N {
            result.coeffs[i] = (self.coeffs[i] + other.coeffs[i]) % Q;
            if result.coeffs[i] < 0 {
                result.coeffs[i] += Q;
            }
        }
        result
    }

    /// Multiply two polynomials in the ring Z_q[X]/(X^N + 1)
    pub fn mul(&self, other: &Poly) -> Poly {
        let mut result = Poly::new();
        let mut temp = [0i64; 2 * N];

        // Standard polynomial multiplication
        for i in 0..N {
            for j in 0..N {
                temp[i + j] += (self.coeffs[i] as i64) * (other.coeffs[j] as i64);
            }
        }

        // Modular reduction by (X^N + 1)
        for i in (N..2 * N - 1).rev() {
            temp[i - N] -= temp[i];
            temp[i] = 0;
        }

        // Reduction by Q
        for (coefficient, raw) in result.coeffs.iter_mut().zip(temp.iter()) {
            let mut val = (raw % (Q as i64)) as i32;
            if val < 0 {
                val += Q;
            }
            *coefficient = val;
        }

        result
    }
}

pub struct KyberState {
    pub public_matrix_a: Vec<Vec<Poly>>,
    pub secret_s: Vec<Poly>,
    pub error_e: Vec<Poly>,
    pub public_t: Vec<Poly>,
}

impl Default for KyberState {
    fn default() -> Self {
        Self::new()
    }
}

impl KyberState {
    pub fn new() -> Self {
        let mut rng = thread_rng();

        // 1. Generate random matrix A
        let mut a = vec![vec![Poly::new(); K]; K];
        for row in &mut a {
            for poly in row {
                for coefficient in &mut poly.coeffs {
                    *coefficient = rng.gen_range(0..Q);
                }
            }
        }

        // 2. Generate small secret vector s and error vector e
        // In real Kyber, these are sampled from a Centered Binomial Distribution
        let mut s = vec![Poly::new(); K];
        let mut e = vec![Poly::new(); K];
        for (secret, error) in s.iter_mut().zip(e.iter_mut()) {
            for (secret_coefficient, error_coefficient) in
                secret.coeffs.iter_mut().zip(error.coeffs.iter_mut())
            {
                *secret_coefficient = rng.gen_range(-2..=2);
                *error_coefficient = rng.gen_range(-2..=2);
            }
        }

        // 3. Compute public key t = A * s + e
        let mut t = vec![Poly::new(); K];
        for (target, (row, error)) in t.iter_mut().zip(a.iter().zip(e.iter())) {
            let mut row_sum = Poly::new();
            for (matrix_poly, secret) in row.iter().zip(s.iter()) {
                row_sum = row_sum.add(&matrix_poly.mul(secret));
            }
            *target = row_sum.add(error);
        }

        KyberState {
            public_matrix_a: a,
            secret_s: s,
            error_e: e,
            public_t: t,
        }
    }

    /// Encrypts a binary payload (e.g., serialized neural weights) into a quantum-resistant ciphertext.
    pub fn encrypt_historical_data(&self, data: &[u8]) -> (Vec<Poly>, Poly) {
        let mut rng = thread_rng();

        // Ephemeral secret r and errors e1, e2
        let mut r = vec![Poly::new(); K];
        let mut e1 = vec![Poly::new(); K];
        let mut e2 = Poly::new();

        for (ephemeral, error) in r.iter_mut().zip(e1.iter_mut()) {
            for (ephemeral_coefficient, error_coefficient) in
                ephemeral.coeffs.iter_mut().zip(error.coeffs.iter_mut())
            {
                *ephemeral_coefficient = rng.gen_range(-2..=2);
                *error_coefficient = rng.gen_range(-2..=2);
            }
        }
        for coefficient in &mut e2.coeffs {
            *coefficient = rng.gen_range(-2..=2);
        }

        // u = A^T * r + e1
        let mut u = vec![Poly::new(); K];
        for (i, (target, error)) in u.iter_mut().zip(e1.iter()).enumerate() {
            let mut col_sum = Poly::new();
            for (row, ephemeral) in self.public_matrix_a.iter().zip(r.iter()) {
                col_sum = col_sum.add(&row[i].mul(ephemeral));
            }
            *target = col_sum.add(error);
        }

        // v = t^T * r + e2 + m * (Q/2)
        let mut v_sum = Poly::new();
        for (public, ephemeral) in self.public_t.iter().zip(r.iter()) {
            v_sum = v_sum.add(&public.mul(ephemeral));
        }

        let mut v = v_sum.add(&e2);

        // Encode the message bits into the polynomial
        let q_half = Q / 2;
        let mut bit_idx = 0;
        for &byte in data {
            for bit in 0..8 {
                if bit_idx >= N {
                    break;
                }
                let bit_val = (byte >> bit) & 1;
                if bit_val == 1 {
                    v.coeffs[bit_idx] = (v.coeffs[bit_idx] + q_half) % Q;
                }
                bit_idx += 1;
            }
        }

        (u, v)
    }
}
