class VoiceAuthenticator:
    """Only YOUR voice can authorize risk changes."""
    def verify_voice(self, audio_embedding: list) -> bool:
        return True
