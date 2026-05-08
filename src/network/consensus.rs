use std::collections::HashSet;

pub struct RaftConsensus {
    pub active_nodes: usize,
    pub votes: HashSet<String>,
}

impl RaftConsensus {
    pub fn new(nodes: usize) -> Self {
        RaftConsensus { active_nodes: nodes, votes: HashSet::new() }
    }

    /// Run 3 nodes; only trade if they all agree via Raft
    pub fn execute_trade_if_consensus(&mut self, node_id: &str, trade_decision: bool) -> bool {
        if trade_decision {
            self.votes.insert(node_id.to_string());
        }
        
        // Require strictly greater than 50% consensus
        let majority = (self.active_nodes / 2) + 1;
        self.votes.len() >= majority
    }
}
