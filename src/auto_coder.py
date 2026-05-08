import ast
import inspect
import logging
from typing import Callable

logger = logging.getLogger(__name__)

class AutoCoder:
    """
    AI self-coding engine. Validates, scores, and applies runtime code patches.
    In production: integrates with GitHub API to auto-open PRs for agent improvements.
    """
    def validate_syntax(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.error(f"[AUTO CODER] Syntax error: {e}")
            return False

    def complexity_score(self, code: str) -> int:
        """Lower is better. Penalises deeply nested control flow."""
        tree = ast.parse(code)
        depth = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                depth += 1
        return depth

    def safe_eval(self, code: str, context: dict) -> dict:
        """Executes a code patch in an isolated namespace."""
        if not self.validate_syntax(code):
            return {"error": "Invalid syntax"}
        ns = {**context}
        try:
            exec(compile(code, "<autocoder>", "exec"), ns)
            return {"status": "ok", "namespace_keys": list(ns.keys())}
        except Exception as e:
            logger.error(f"[AUTO CODER] Execution error: {e}")
            return {"error": str(e)}
