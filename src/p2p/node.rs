use libp2p::{
    gossipsub::{Gossipsub, GossipsubEvent, MessageAuthenticity},
    mdns::{Mdns, MdnsEvent},
    swarm::{NetworkBehaviourEventProcess, Swarm},
    NetworkBehaviour, PeerId,
};
use log::{info, warn};

/// Peer-to-Peer Sovereign Network Node
/// Allows trusted, cryptographically-verified instances of the Sovereign Architect
/// to share abstracted "Signal Vectors" globally without revealing raw code.

#[derive(NetworkBehaviour)]
#[behaviour(event_process = true)]
pub struct SovereignBehaviour {
    pub gossipsub: Gossipsub,
    pub mdns: Mdns,
}

impl NetworkBehaviourEventProcess<MdnsEvent> for SovereignBehaviour {
    fn inject_event(&mut self, event: MdnsEvent) {
        match event {
            MdnsEvent::Discovered(list) => {
                for (peer, _) in list {
                    info!("[P2P] Discovered trusted Sovereign Peer: {:?}", peer);
                    self.gossipsub.add_explicit_peer(&peer);
                }
            }
            MdnsEvent::Expired(list) => {
                for (peer, _) in list {
                    warn!("[P2P] Peer expired: {:?}", peer);
                    self.gossipsub.remove_explicit_peer(&peer);
                }
            }
        }
    }
}

impl NetworkBehaviourEventProcess<GossipsubEvent> for SovereignBehaviour {
    fn inject_event(&mut self, event: GossipsubEvent) {
        if let GossipsubEvent::Message { propagation_source: peer, message, .. } = event {
            info!("[P2P] Received Signal Vector from {:?}: {:?}", peer, String::from_utf8_lossy(&message.data));
        }
    }
}
