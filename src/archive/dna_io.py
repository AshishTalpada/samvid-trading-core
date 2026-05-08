class DNAMemory:
    """Theoretical: 10k-year record using DNA base pairs."""
    def encode_data_to_atcg(self, binary_data: str) -> str:
        # 00 -> A, 01 -> C, 10 -> G, 11 -> T
        mapping = {"00": "A", "01": "C", "10": "G", "11": "T"}
        dna = ""
        for i in range(0, len(binary_data), 2):
            chunk = binary_data[i:i+2]
            if len(chunk) == 2:
                dna += mapping[chunk]
        return dna
