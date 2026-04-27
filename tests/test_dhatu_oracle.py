from src.dhatu_oracle import DhatuOracle


def test_oracle_initialization():
    oracle = DhatuOracle()
    assert oracle.current_state == "NEUTRAL"
    assert oracle.confidence == 0

def test_macro_bias_synthesis():
    oracle = DhatuOracle()
    # Test Bearish Synthesis (High VIX, Inverted Yields)
    mock_data = {
        'vix': 35.0,
        'yield_10y': 3.5,
        'yield_2y': 4.5,  # Inverted
        'oil': 95.0
    }
    bias = oracle.calculate_bias(mock_data)
    assert bias == "BEARISH"
    assert oracle.current_state == "KSHAYA" # Decay/Decline

def test_macro_bias_bullish():
    oracle = DhatuOracle()
    # Test Bullish Synthesis (Low VIX, Normal Yields)
    mock_data = {
        'vix': 12.0,
        'yield_10y': 4.5,
        'yield_2y': 3.5,
        'oil': 75.0
    }
    bias = oracle.calculate_bias(mock_data)
    assert bias == "BULLISH"
    assert oracle.current_state == "VRIDDHI" # Growth

def test_blackswan_detection():
    oracle = DhatuOracle()
    # Extreme VIX spike
    mock_data = {'vix': 85.0}
    is_safe = oracle.check_safety(mock_data)
    assert is_safe is False
