class CompilerFlags:
    """Stores the specific GCC/Clang flags used for instruction specialization."""
    FLAGS = ["-march=native", "-O3", "-flto", "-mavx512f"]

    def get_flags(self) -> list:
        return self.FLAGS
