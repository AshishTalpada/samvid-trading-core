// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ApexArchive {
    // Immutable ledger of every decision made.
    struct Decision {
        string tradeId;
        string justificationHash;
        uint256 timestamp;
        bool successful;
    }
    
    Decision[] public archive;
    address public owner;

    constructor() { owner = msg.sender; }
    
    modifier onlyOwner() { require(msg.sender == owner, "Unauthorized"); _; }

    function logDecision(string memory _id, string memory _hash, bool _success) public onlyOwner {
        archive.push(Decision({
            tradeId: _id,
            justificationHash: _hash,
            timestamp: block.timestamp,
            successful: _success
        }));
    }

    function getDecisionCount() public view returns (uint256) {
        return archive.length;
    }
}
