class LogicVetter:
    """
    Kolmogorov-complexity inspired vetter: simpler theses with fewer assumptions
    are trusted more than complex multi-factor theses.
    """
    def calculate_complexity(self, thesis_factors: list[str]) -> float:
        return float(len(thesis_factors))

    def vetting_score(self, thesis_factors: list[str], max_factors: int = 5) -> float:
        complexity = self.calculate_complexity(thesis_factors)
        score = max(0.0, 1.0 - (complexity - 1) / max_factors)
        return round(score, 4)

    def is_trustworthy(self, thesis_factors: list[str], threshold: float = 0.5) -> bool:
        return self.vetting_score(thesis_factors) >= threshold
