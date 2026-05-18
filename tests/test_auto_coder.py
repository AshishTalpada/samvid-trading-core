from src.auto_coder import AutoCoder


def test_safe_eval_validates_without_execution(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_ALLOW_AUTOCODER_EXEC", raising=False)

    result = AutoCoder().safe_eval("answer = value + 1", {"value": 41})

    assert result == {"status": "validated", "executed": False}


def test_safe_eval_blocks_imports():
    result = AutoCoder().safe_eval("import os\nanswer = os.getcwd()", {})

    assert result["error"] == "Blocked syntax: Import"


def test_safe_eval_restricted_execution(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_ALLOW_AUTOCODER_EXEC", "1")

    result = AutoCoder().safe_eval("answer = sum([1, 2, 3])", {})

    assert result["status"] == "ok"
    assert result["executed"] is True
    assert "answer" in result["namespace_keys"]
