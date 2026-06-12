from types import SimpleNamespace
from unittest.mock import MagicMock

from embedding_engine import SharedEmbeddingEngine


def test_embedding_engine_prefers_cached_model(monkeypatch) -> None:
    model = object()
    factory = MagicMock(return_value=model)
    monkeypatch.setattr(
        "importlib.import_module",
        lambda name: SimpleNamespace(TextEmbedding=factory),
    )
    monkeypatch.setattr("vault.Vault.get", lambda *_args: "BAAI/bge-small-en-v1.5")
    engine = SharedEmbeddingEngine()
    engine._model = None

    assert engine._get_model() is model
    factory.assert_called_once_with("BAAI/bge-small-en-v1.5", local_files_only=True)


def test_embedding_engine_allows_network_fetch_only_after_cache_miss(monkeypatch) -> None:
    model = object()
    factory = MagicMock(side_effect=[ValueError("cache miss"), model])
    monkeypatch.setattr(
        "importlib.import_module",
        lambda name: SimpleNamespace(TextEmbedding=factory),
    )
    monkeypatch.setattr("vault.Vault.get", lambda *_args: "BAAI/bge-small-en-v1.5")
    engine = SharedEmbeddingEngine()
    engine._model = None

    assert engine._get_model() is model
    assert factory.call_args_list[0].kwargs == {"local_files_only": True}
    assert factory.call_args_list[1].kwargs == {}
