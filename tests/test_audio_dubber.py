"""
tests/test_audio_dubber.py
Tests for audio/live_dub.LiveAudioDubber (non-TTS logic only).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "audio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestLiveAudioDubber:
    def setup_method(self):
        from live_dub import LiveAudioDubber
        self.dubber = LiveAudioDubber()

    def teardown_method(self):
        self.dubber.stop()

    def test_announce_puts_to_queue(self):
        self.dubber.announce("Trade executed")
        assert self.dubber._queue.qsize() == 1

    def test_announce_multiple_messages(self):
        for i in range(5):
            self.dubber.announce(f"Message {i}")
        assert self.dubber._queue.qsize() == 5

    def test_announce_drops_when_full(self):
        from live_dub import LiveAudioDubber
        small_dubber = LiveAudioDubber()
        # Fill the queue (maxsize=20)
        for i in range(20):
            small_dubber.announce(f"msg {i}")
        # This one should be dropped silently
        small_dubber.announce("overflow")
        assert small_dubber._queue.qsize() == 20

    def test_announce_trade_formats_message(self):
        self.dubber.announce_trade("BUY", "AAPL", 185.50)
        msg = self.dubber._queue.get_nowait()
        assert "BUY" in msg
        assert "AAPL" in msg
        assert "185.50" in msg

    def test_start_sets_running_flag(self):
        self.dubber.start()
        assert self.dubber._running is True
        assert self.dubber._thread is not None

    def test_stop_clears_running_flag(self):
        self.dubber.start()
        self.dubber.stop()
        assert self.dubber._running is False

    def test_start_stop_idempotent(self):
        self.dubber.start()
        self.dubber.stop()
        # No exceptions; state is clean
        assert self.dubber._running is False
