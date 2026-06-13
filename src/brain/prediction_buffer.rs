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
        if self.capacity == 0 {
            return;
        }
        let mut buf = self
            .buffer
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if buf.len() >= self.capacity {
            buf.pop_front();
        }
        buf.push_back(branch);
    }

    pub fn pop_best(&self) -> Option<DecisionBranch> {
        let mut buf = self
            .buffer
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let best = buf
            .iter()
            .enumerate()
            .filter(|(_, branch)| branch.probability.is_finite())
            .max_by(|a, b| a.1.probability.total_cmp(&b.1.probability))
            .map(|(i, _)| i);
        best.map(|i| buf.remove(i).unwrap())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn branch(scenario: &str, probability: f64) -> DecisionBranch {
        DecisionBranch {
            scenario: scenario.to_string(),
            probability,
            recommended_action: "HOLD".to_string(),
        }
    }

    #[test]
    fn bounded_buffer_evicts_oldest_and_returns_highest_probability() {
        let buffer = PredictionBuffer::new(2);
        buffer.push(branch("old", 0.99));
        buffer.push(branch("middle", 0.40));
        buffer.push(branch("latest", 0.70));

        assert_eq!(buffer.pop_best().unwrap().scenario, "latest");
        assert_eq!(buffer.pop_best().unwrap().scenario, "middle");
        assert!(buffer.pop_best().is_none());
    }

    #[test]
    fn zero_capacity_buffer_stays_empty() {
        let buffer = PredictionBuffer::new(0);
        buffer.push(branch("ignored", 1.0));

        assert!(buffer.pop_best().is_none());
    }

    #[test]
    fn non_finite_probabilities_are_never_selected() {
        let buffer = PredictionBuffer::new(3);
        buffer.push(branch("nan", f64::NAN));
        buffer.push(branch("valid", 0.5));

        assert_eq!(buffer.pop_best().unwrap().scenario, "valid");
        assert!(buffer.pop_best().is_none());
    }
}
