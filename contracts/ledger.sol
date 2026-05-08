// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ImmortalLedger {
    struct Trade {
        string ticker;
        uint256 price;
        uint256 volume;
    }
    Trade[] public trades;

    function recordTrade(string memory _ticker, uint256 _price, uint256 _volume) public {
        trades.push(Trade(_ticker, _price, _volume));
    }
}
