// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ContractInsurance {
    // Automated DeFi insurance for trading positions
    mapping(address => uint256) public coverage;

    function buyCoverage() public payable {
        coverage[msg.sender] += msg.value;
    }
}
