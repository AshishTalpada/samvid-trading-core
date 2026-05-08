class DebtCycleTracker:
    def __init__(self, long_term_debt_to_gdp: float):
        self.debt_ratio = long_term_debt_to_gdp

    def get_macro_risk(self) -> str:
        if self.debt_ratio > 1.3:
            return "DELEVERAGING_RISK"
        return "EXPANSION"
