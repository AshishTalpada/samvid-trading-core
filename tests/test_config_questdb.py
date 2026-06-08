from unittest.mock import patch

import config


def test_questdb_explicit_enable_bypasses_probe() -> None:
    with patch("config._probe_questdb", return_value=False) as probe:
        assert config._resolve_questdb_enabled("true", "questdb", 9009) is True

    probe.assert_not_called()


def test_questdb_explicit_disable_bypasses_probe() -> None:
    with patch("config._probe_questdb", return_value=True) as probe:
        assert config._resolve_questdb_enabled("0", "questdb", 9009) is False

    probe.assert_not_called()


def test_questdb_auto_detect_uses_configured_endpoint() -> None:
    with patch("config._probe_questdb", return_value=True) as probe:
        assert config._resolve_questdb_enabled("", "questdb", 19009) is True

    probe.assert_called_once_with("questdb", 19009)
