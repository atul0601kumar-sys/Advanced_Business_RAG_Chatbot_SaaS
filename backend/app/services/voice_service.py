from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.dependencies.auth import get_workspace_member
from app.models import User
from app.schemas.voice import (
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
    VoiceTranscriptionRequest,
    VoiceTranscriptionResponse,
)


@dataclass
class SynthesizedAudio:
    audio_bytes: bytes
    mime_type: str
    provider: str


class SpeechToTextProvider(ABC):
    @abstractmethod
    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str | None) -> VoiceTranscriptionResponse:
        raise NotImplementedError


class TextToSpeechProvider(ABC):
    @abstractmethod
    def synthesize(self, *, text: str, voice_style: str | None, format: str) -> SynthesizedAudio:
        raise NotImplementedError


class OpenAISpeechToTextProvider(SpeechToTextProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str | None) -> VoiceTranscriptionResponse:
        if not self.settings.openai_api_key:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Voice transcription is not configured.")

        extension = mimetypes.guess_extension(mime_type) or ".webm"
        boundary = f"----VoiceFormBoundary{uuid.uuid4().hex}"
        parts: list[bytes] = []

        def add_text_field(name: str, value: str) -> None:
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        add_text_field("model", self.settings.openai_transcription_model)
        add_text_field("response_format", "json")
        if language:
            add_text_field("language", language)
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="voice-input{extension}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8")
        )
        parts.append(audio_bytes)
        parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)

        request = urllib_request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            detail = self._extract_error(exc, "Voice transcription failed.")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
        except urllib_error.URLError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Voice transcription request could not reach the provider.") from exc

        transcript = (payload.get("text") or "").strip()
        if not transcript:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Voice transcription returned an empty transcript.")
        return VoiceTranscriptionResponse(transcript=transcript, provider="openai")

    def _extract_error(self, exc: urllib_error.HTTPError, fallback: str) -> str:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            return fallback
        return payload.get("error", {}).get("message") or fallback


class OpenAITextToSpeechProvider(TextToSpeechProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def synthesize(self, *, text: str, voice_style: str | None, format: str) -> SynthesizedAudio:
        if not self.settings.openai_api_key:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Voice synthesis is not configured.")
        payload = {
            "model": self.settings.openai_tts_model,
            "input": text,
            "voice": (voice_style or "alloy").strip() or "alloy",
            "format": format or self.settings.voice_default_tts_format,
        }
        request = urllib_request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=60) as response:
                audio_bytes = response.read()
        except urllib_error.HTTPError as exc:
            detail = self._extract_error(exc, "Voice synthesis failed.")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
        except urllib_error.URLError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Voice synthesis request could not reach the provider.") from exc
        return SynthesizedAudio(
            audio_bytes=audio_bytes,
            mime_type=f"audio/{payload['format']}",
            provider="openai",
        )

    def _extract_error(self, exc: urllib_error.HTTPError, fallback: str) -> str:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            return fallback
        return payload.get("error", {}).get("message") or fallback


class VoiceService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        stt_provider: SpeechToTextProvider | None = None,
        tts_provider: TextToSpeechProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.stt_provider = stt_provider or self._build_stt_provider()
        self.tts_provider = tts_provider or self._build_tts_provider()

    def transcribe(
        self,
        db: Session,
        *,
        current_user: User | None,
        workspace_id: uuid.UUID,
        payload: VoiceTranscriptionRequest,
    ) -> VoiceTranscriptionResponse:
        if current_user is not None:
            get_workspace_member(workspace_id, current_user, db)
        audio_bytes = self._decode_audio(payload.audio_base64)
        return self.stt_provider.transcribe(audio_bytes=audio_bytes, mime_type=payload.mime_type, language=payload.language)

    def synthesize(
        self,
        db: Session,
        *,
        current_user: User | None,
        workspace_id: uuid.UUID,
        payload: VoiceSynthesisRequest,
    ) -> VoiceSynthesisResponse:
        if current_user is not None:
            get_workspace_member(workspace_id, current_user, db)
        synthesized = self.tts_provider.synthesize(text=payload.text, voice_style=payload.voice_style, format=payload.format)
        return VoiceSynthesisResponse(
            audio_base64=base64.b64encode(synthesized.audio_bytes).decode("utf-8"),
            mime_type=synthesized.mime_type,
            provider=synthesized.provider,
        )

    def _build_stt_provider(self) -> SpeechToTextProvider:
        if self.settings.voice_backend_input_provider == "openai":
            return OpenAISpeechToTextProvider(self.settings)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unsupported voice input provider.")

    def _build_tts_provider(self) -> TextToSpeechProvider:
        if self.settings.voice_backend_output_provider == "openai":
            return OpenAITextToSpeechProvider(self.settings)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unsupported voice output provider.")

    def _decode_audio(self, payload: str) -> bytes:
        try:
            return base64.b64decode(payload.encode("utf-8"), validate=True)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voice audio payload is invalid.") from exc
