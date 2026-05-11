use libp2p::{
    gossipsub,
    mdns,
    swarm::NetworkBehaviour,
};
use log::{info, warn};

/// Peer-to-Peer Sovereign Network Node
/// Allows trusted, cryptographically-verified instances of the Sovereign Architect
/// to share abstracted "Signal Vectors" globally without revealing raw code.

#[derive(NetworkBehaviour)]
#[behaviour(to_swarm = "SovereignBehaviourEvent")]
pub struct SovereignBehaviour {
    pub gossipsub: gossipsub::Behaviour,
    pub mdns: mdns::tokio::Behaviour,
}

#[derive(Debug)]
pub enum SovereignBehaviourEvent {
    Gossipsub(gossipsub::Event),
    Mdns(mdns::Event),
}

impl From<gossipsub::Event> for SovereignBehaviourEvent {
    fn from(event: gossipsub::Event) -> Self {
        SovereignBehaviourEvent::Gossipsub(event)
    }
}

impl From<mdns::Event> for SovereignBehaviourEvent {
    fn from(event: mdns::Event) -> Self {
        SovereignBehaviourEvent::Mdns(event)
    }
}

impl SovereignBehaviour {
    /// Handles events coming from the sub-behaviours.
    /// This should be called from the main Swarm event loop.
    pub fn handle_event(&mut self, event: SovereignBehaviourEvent) {
        match event {
            SovereignBehaviourEvent::Mdns(mdns_event) => {
                match mdns_event {
                    mdns::Event::Discovered(list) => {
                        for (peer, _) in list {
                            info!("[P2P] Discovered trusted Sovereign Peer: {:?}", peer);
                            self.gossipsub.add_explicit_peer(&peer);
                        }
                    }
                    mdns::Event::Expired(list) => {
                        for (peer, _) in list {
                            warn!("[P2P] Peer expired: {:?}", peer);
                            self.gossipsub.remove_explicit_peer(&peer);
                        }
                    }
                }
            }
            SovereignBehaviourEvent::Gossipsub(gossip_event) => {
                if let gossipsub::Event::Message { propagation_source: peer, message, .. } = gossip_event {
                    info!("[P2P] Received Signal Vector from {:?}: {:?}", peer, String::from_utf8_lossy(&message.data));
                }
            }
        }
    }
}
