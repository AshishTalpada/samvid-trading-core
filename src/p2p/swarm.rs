use libp2p::{
    gossipsub::{Gossipsub, GossipsubConfigBuilder, MessageAuthenticity, IdentTopic as Topic, GossipsubEvent},
    identity, PeerId, Swarm,
};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::time::Duration;

/// Deep Dive: Swarm Swarms (P2P Gossip Network)
/// Allows multiple distributed Sovereign nodes (running across different clouds/countries)
/// to securely discover each other and share cryptographic Alpha signals in real-time.
pub struct SovereignSwarm {
    pub local_peer_id: PeerId,
    pub topic: Topic,
}

impl SovereignSwarm {
    pub fn new() -> Self {
        // Generate a random Ed25519 keypair
        let local_key = identity::Keypair::generate_ed25519();
        let local_peer_id = PeerId::from(local_key.public());
        println!("[SWARM] Local Sovereign Node Identity: {:?}", local_peer_id);

        // Define a strict, application-specific pubsub topic
        let topic = Topic::new("sovereign-alpha-stream-v1");

        SovereignSwarm {
            local_peer_id,
            topic,
        }
    }

    /// Sets up the GossipSub behavior with strict anti-spam and validation routing
    pub fn build_gossipsub(&self, local_key: identity::Keypair) -> Gossipsub {
        // Custom message hashing to prevent duplicate floods
        let message_id_fn = |message: &libp2p::gossipsub::GossipsubMessage| {
            let mut s = DefaultHasher::new();
            message.data.hash(&mut s);
            libp2p::gossipsub::MessageId::from(s.finish().to_string())
        };

        // Strict gossipsub configuration for low-latency HFT message propagation
        let gossipsub_config = GossipsubConfigBuilder::default()
            .heartbeat_interval(Duration::from_millis(500)) // Very fast heartbeats
            .validation_mode(libp2p::gossipsub::ValidationMode::Strict) // Strict crypto validation
            .message_id_fn(message_id_fn)
            .build()
            .expect("Valid GossipSub config");

        // Bind the behavior
        let mut gossipsub = Gossipsub::new(MessageAuthenticity::Signed(local_key), gossipsub_config)
            .expect("Correct configuration");

        gossipsub.subscribe(&self.topic).unwrap();
        gossipsub
    }
}
