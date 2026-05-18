use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// Phase 3: The Fast Brain - Native Execution Engine
/// This module replaces the Python asyncio quorum voting logic with a native, 
/// zero-allocation Rust loop, vastly improving latency in the critical path.
#[pyclass]
pub struct FastDecisionEngine {
    required_agents: Vec<String>,
}

#[pymethods]
impl FastDecisionEngine {
    #[new]
    pub fn new() -> Self {
        FastDecisionEngine {
            required_agents: vec![
                "Agent_A".to_string(), "Agent_B".to_string(), "Agent_C".to_string(),
                "Agent_D".to_string(), "Agent_E".to_string(), "Agent_F".to_string(),
                "Agent_G".to_string(), "Risk_Guard".to_string(), "Dhatu_Oracle".to_string(),
                "Swarm_Predictor".to_string(), "Mind_Ultrathink".to_string()
            ],
        }
    }

    pub fn evaluate<'py>(&self, py: Python<'py>, context: &'py PyDict, agent_outputs: &'py PyList) -> PyResult<&'py PyDict> {
        let is_probe: bool = context.get_item("is_probe")?.map(|v| v.extract().unwrap_or(false)).unwrap_or(false);
        let regime: String = context.get_item("regime")?.map(|v| v.extract().unwrap_or("UNKNOWN".to_string())).unwrap_or("UNKNOWN".to_string());
        let safe_mode_active: bool = context.get_item("safe_mode_active")?.map(|v| v.extract().unwrap_or(false)).unwrap_or(false);
        
        let context_ts: f64 = match context.get_item("timestamp")? {
            Some(v) => v.extract().unwrap_or(0.0),
            None => 0.0,
        };

        if context_ts == 0.0 {
            return self.reject(py, "Decision Cycle Fault: Context missing timestamp.");
        }

        let mut yes_votes = 0.0;
        let mut _no_votes = 0;
        let mut _abstain_votes = 0;
        let mut total_confidence = 0.0;
        let mut active_voters = 0;
        let mut agent_d_edge_crowded = false;
        
        let num_agents = agent_outputs.len();

        if num_agents < self.required_agents.len() && !is_probe {
            return self.reject(py, &format!("Quorum Violation: Expected at least {}, got {}.", self.required_agents.len(), num_agents));
        }

        for i in 0..num_agents {
            let out_any = agent_outputs.get_item(i)?;
            let out: &PyDict = out_any.downcast()?;
            let agent: String = out.get_item("agent")?.map(|v| v.extract().unwrap_or("UNKNOWN".to_string())).unwrap_or("UNKNOWN".to_string());
            let vote: String = out.get_item("vote")?.map(|v| v.extract().unwrap_or("ABSTAIN".to_string())).unwrap_or("ABSTAIN".to_string());
            let confidence: f64 = out.get_item("confidence")?.map(|v| v.extract().unwrap_or(0.0)).unwrap_or(0.0);
            let agent_ts: f64 = out.get_item("timestamp")?.map(|v| v.extract().unwrap_or(0.0)).unwrap_or(0.0);

            // Fast path numeric drift check
            let mut c_ts = context_ts;
            let mut a_ts = agent_ts;
            if c_ts > 1e15 { c_ts /= 1e9; }
            if a_ts > 1e15 { a_ts /= 1e9; }
            
            let drift = (a_ts - c_ts).abs();
            if drift > 60.0 {
                continue; // Too slow
            }

            if agent == "Risk_Guard" && vote == "NO" && !is_probe {
                return self.reject(py, "🛑 HARD VETO: Risk_Guard blocked the trade (Safety Protocol).");
            }
            if agent == "Mind_Ultrathink" && vote == "NO" && !is_probe {
                return self.reject(py, "🛑 COGNITIVE VETO: Mind_Ultrathink REJECTED the trade.");
            }

            if vote == "YES" {
                if agent == "Agent_D" {
                    yes_votes += 2.0; // 2x weighting for Agent_D
                    if let Ok(Some(meta)) = out.get_item("metadata") {
                        if let Ok(m_dict) = meta.downcast::<PyDict>() {
                            if let Ok(Some(crowded)) = m_dict.get_item("edge_crowded") {
                                agent_d_edge_crowded = crowded.extract().unwrap_or(false);
                            }
                        }
                    }
                } else {
                    yes_votes += 1.0;
                }
            } else if vote == "NO" {
                _no_votes += 1;
            } else {
                _abstain_votes += 1;
                continue;
            }

            total_confidence += confidence;
            active_voters += 1;
        }

        let avg_confidence = if active_voters > 0 { total_confidence / active_voters as f64 } else { 0.0 };

        if safe_mode_active {
            let actual_threshold = yes_votes / self.required_agents.len() as f64;
            if actual_threshold >= 0.50 && (avg_confidence > 0.70 || is_probe) {
                return self.execute(py, avg_confidence, "🏛️ SAFE-MODE SUCCESS", agent_d_edge_crowded);
            } else {
                return self.reject(py, "🛑 SAFE-MODE REJECTION: Consensus < 50%.");
            }
        } else {
            let min_required = if regime == "CHOPPY" || regime == "VOLATILE" { 4.0 } else { 5.0 };
            let vote_ratio = if active_voters > 0 { yes_votes / active_voters as f64 } else { 0.0 };
            
            if is_probe {
                if yes_votes > 0.0 {
                    return self.execute(py, avg_confidence, "PHANTOM PROBE SUCCESS", agent_d_edge_crowded);
                } else {
                    return self.reject(py, "PHANTOM PROBE FAILURE");
                }
            }

            if yes_votes >= min_required && vote_ratio >= 0.60 && avg_confidence > 0.60 {
                return self.execute(py, avg_confidence, "Quorum Met", agent_d_edge_crowded);
            } else {
                return self.reject(py, "Consensus Failure");
            }
        }
    }

    fn reject<'py>(&self, py: Python<'py>, reason: &str) -> PyResult<&'py PyDict> {
        let dict = PyDict::new(py);
        dict.set_item("decision", "REJECT")?;
        dict.set_item("confidence", 0.0)?;
        dict.set_item("reason", reason)?;
        Ok(dict)
    }

    fn execute<'py>(&self, py: Python<'py>, confidence: f64, reason: &str, ghost_expansion: bool) -> PyResult<&'py PyDict> {
        let dict = PyDict::new(py);
        dict.set_item("decision", "EXECUTE")?;
        dict.set_item("confidence", confidence)?;
        dict.set_item("reason", reason)?;
        if ghost_expansion {
            dict.set_item("execution_mode", "GHOST_EXPANSION")?;
            dict.set_item("stop_multiplier", 1.35)?;
            dict.set_item("size_multiplier", 0.75)?;
        }
        Ok(dict)
    }
}
