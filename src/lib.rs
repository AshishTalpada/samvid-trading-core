// src/lib.rs
// Sovereign Native Entry Point

use pyo3::prelude::*;

pub mod ibkr_streamer;
pub mod network_core;
pub mod arbitrage;
pub mod micro_arb;
pub mod dark_pool;
pub mod lob_analyzer;
pub mod order_signer;
pub mod security_core;
pub mod resilience_core;
pub mod prediction_buffer;
pub mod consensus;
pub mod signed_bus;
pub mod slicer;
pub mod universal_bridge;
pub mod network_layer;
pub mod nasdaq;
pub mod swarm;
pub mod node;
pub mod network;
pub mod aegis_v4;
pub mod recovery;
pub mod cold_storage;
pub mod zkp;
pub mod q_safe;
pub mod lattice;

#[pymodule]
fn sovereign_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ibkr_streamer::stream_ticks, m)?)?;
    // Add other functions as needed
    Ok(())
}
