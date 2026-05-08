class PatentAgent:
    """Tracks patent filing velocity to identify innovation leaders."""
    def calculate_velocity(self, patent_counts: list[int]) -> float:
        """Returns average patents per period."""
        if not patent_counts:
            return 0.0
        return sum(patent_counts) / len(patent_counts)

    def is_accelerating(self, patent_counts: list[int]) -> bool:
        if len(patent_counts) < 3:
            return False
        return patent_counts[-1] > patent_counts[-2] > patent_counts[-3]
