// src/lib.rs
// Sovereign Native Entry Point
#![allow(non_local_definitions)]

use pyo3::prelude::*;

pub mod arbitrage;
pub mod dark_pool;
pub mod ibkr_streamer;
pub mod lob_analyzer;
pub mod micro_arb;
pub mod network_core;
pub mod order_signer;
pub mod resilience_core;
pub mod security_core;

#[path = "brain/prediction_buffer.rs"]
pub mod prediction_buffer;

#[path = "network/consensus.rs"]
pub mod consensus;
#[path = "execution/decision_engine.rs"]
pub mod decision_engine;
pub mod network_layer;
#[path = "execution/signed_bus.rs"]
pub mod signed_bus;
#[path = "execution/slicer.rs"]
pub mod slicer;
#[path = "execution/universal_bridge.rs"]
pub mod universal_bridge;

#[path = "feeds/nasdaq.rs"]
pub mod nasdaq;

#[path = "p2p/swarm.rs"]
pub mod swarm;

#[path = "p2p/node.rs"]
pub mod node;

#[path = "p2p/network.rs"]
pub mod network;

#[path = "resilience/aegis_v4.rs"]
pub mod aegis_v4;

#[path = "resilience/recovery.rs"]
pub mod recovery;

#[path = "wallets/cold_storage.rs"]
pub mod cold_storage;

#[path = "../quarantine/zkp.rs"]
pub mod zkp;

#[path = "../quarantine/q_safe.rs"]
pub mod q_safe;

#[path = "../quarantine/lattice.rs"]
pub mod lattice;

#[pymodule]
fn sovereign_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ibkr_streamer::stream_ticks, m)?)?;
    m.add_class::<decision_engine::FastDecisionEngine>()?;
    // Add other functions as needed
    Ok(())
}
