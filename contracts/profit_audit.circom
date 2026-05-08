pragma circom 2.0.0;

template ProfitAudit() {
    signal input profit;
    signal input threshold;
    signal output isProfitable;

    isProfitable <== profit > threshold ? 1 : 0;
}

component main = ProfitAudit();
