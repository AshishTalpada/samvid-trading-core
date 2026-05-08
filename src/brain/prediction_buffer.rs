// src/brain/prediction_buffer.rs
// Pre-computation buffer that calculates the next 3 decision branches
// before the market forces a decision, eliminating computation latency
// from the critical execution path.
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

#[derive(Clone, Debug)]
pub struct DecisionBranch {
    pub scenario: String,
    pub probability: f64,
    pub recommended_action: String,
}

pub struct PredictionBuffer {
    buffer: Arc<Mutex<VecDeque<DecisionBranch>>>,
    capacity: usize,
}

impl PredictionBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            buffer: Arc::new(Mutex::new(VecDeque::with_capacity(capacity))),
            capacity,
        }
    }

    pub fn push(&self, branch: DecisionBranch) {
        let mut buf = self.buffer.lock().unwrap();
        if buf.len() >= self.capacity {
            buf.pop_front();
        }
        buf.push_back(branch);
    }

    pub fn pop_best(&self) -> Option<DecisionBranch> {
        let mut buf = self.buffer.lock().unwrap();
        let best = buf.iter().enumerate()
            .max_by(|a, b| a.1.probability.partial_cmp(&b.1.probability).unwrap())
            .map(|(i, _)| i);
        best.map(|i| buf.remove(i).unwrap())
    }
}
