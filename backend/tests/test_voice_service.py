import base64
import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import User, Workspace, WorkspaceMember
from app.schemas.voice import VoiceSynthesisRequest, VoiceTranscriptionRequest
from app.services.voice_service import SynthesizedAudio, TextToSpeechProvider, VoiceService, SpeechToTextProvider


class FakeSpeechToTextProvider(SpeechToTextProvider):
    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str | None):
        return type("FakeTranscription", (), {"transcript": f"{mime_type}:{len(audio_bytes)}", "provider": "fake-stt"})()


class FakeTextToSpeechProvider(TextToSpeechProvider):
    def synthesize(self, *, text: str, voice_style: str | None, format: str):
        return SynthesizedAudio(
          audio_bytes=f"{voice_style or 'default'}:{text}".encode("utf-8"),
          mime_type="audio/mp3",
          provider="fake-tts",
        )


class VoiceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_workspace(self):
        with self.SessionLocal() as db:
            user = User(
                email="voice-owner@example.com",
                full_name="Voice Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="Voice Workspace",
                slug=f"voice-{uuid.uuid4().hex[:8]}",
                description="Voice tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()
            return user.id, workspace.id

    def test_transcribe_and_synthesize_with_provider_abstraction(self) -> None:
        user_id, workspace_id = self._seed_workspace()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            service = VoiceService(
                stt_provider=FakeSpeechToTextProvider(),
                tts_provider=FakeTextToSpeechProvider(),
            )

            transcript = service.transcribe(
                db,
                current_user=user,
                workspace_id=workspace_id,
                payload=VoiceTranscriptionRequest(
                    workspace_id=workspace_id,
                    audio_base64=base64.b64encode(b"voice").decode("utf-8"),
                    mime_type="audio/webm",
                ),
            )
            self.assertEqual(transcript.provider, "fake-stt")
            self.assertEqual(transcript.transcript, "audio/webm:5")

            audio = service.synthesize(
                db,
                current_user=user,
                workspace_id=workspace_id,
                payload=VoiceSynthesisRequest(
                    workspace_id=workspace_id,
                    text="Hello",
                    voice_style="alloy",
                    format="mp3",
                ),
            )
            self.assertEqual(audio.provider, "fake-tts")
            self.assertEqual(base64.b64decode(audio.audio_base64.encode("utf-8")), b"alloy:Hello")


if __name__ == "__main__":
    unittest.main()
