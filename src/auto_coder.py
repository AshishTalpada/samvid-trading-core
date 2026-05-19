import ast
import inspect
import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)


_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

_BLOCKED_NODES = (
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Nonlocal,
    ast.Try,
    ast.With,
)
_BLOCKED_CALLS = {"__import__", "eval", "exec", "open", "compile", "input", "globals", "locals"}


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

    def validate_safety(self, code: str) -> tuple[bool, str]:
        """Reject code shapes that can escape the evaluation sandbox."""
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, f"Invalid syntax: {exc}"

        for node in ast.walk(tree):
            if isinstance(node, _BLOCKED_NODES):
                return False, f"Blocked syntax: {type(node).__name__}"
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in _BLOCKED_CALLS:
                    return False, f"Blocked call: {func.id}"
                if isinstance(func, ast.Attribute) and func.attr.startswith("__"):
                    return False, f"Blocked dunder call: {func.attr}"
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return False, f"Blocked dunder attribute: {node.attr}"

        return True, "ok"

    def safe_eval(self, code: str, context: dict) -> dict:
        """Validate a code patch and optionally execute it in a restricted namespace."""
        if not self.validate_syntax(code):
            return {"error": "Invalid syntax"}
        is_safe, reason = self.validate_safety(code)
        if not is_safe:
            return {"error": reason}
        if os.getenv("SOVEREIGN_ALLOW_AUTOCODER_EXEC", "0") != "1":
            return {"status": "validated", "executed": False}

        ns = {"__builtins__": _SAFE_BUILTINS, **context}
        try:
            exec(compile(code, "<autocoder>", "exec"), ns)
            return {
                "status": "ok",
                "executed": True,
                "namespace_keys": [k for k in ns.keys() if k != "__builtins__"],
            }
        except Exception as e:
            logger.error(f"[AUTO CODER] Execution error: {e}")
            return {"error": str(e)}
