"""Motor modular de áudio (STT e TTS PT-BR) para interação por voz no SUS Cidadão.

Prioridades de síntese de voz (TTS):
1. Neural online PT-BR (`edge-tts`, voz `pt-BR-FranciscaNeural`) -> MP3 Base64.
2. Offline nativo macOS (`/usr/bin/say -v Luciana` em formato AAC/M4A) quando disponível.
3. Fallback transparente (`provider="browser_speech_synthesis"`) para uso via Web Speech API no cliente.

Transcrição (STT) no servidor:
- Gemini Audio (`GEMINI_API_KEY`) ou OpenAI Whisper (`OPENAI_API_KEY`) via `httpx`.
- Sem chaves externas configuradas, o cliente Web utiliza reconhecimento nativo em tempo real (`SpeechRecognition` PT-BR).
"""

from __future__ import annotations

import asyncio
import base64
import importlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class STTResult:
    """Resultado de transcrição de áudio para texto PT-BR."""

    text: str
    provider: str
    language: str = "pt-BR"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TTSResult:
    """Resultado de síntese de voz (MP3/M4A Base64 ou fallback cliente)."""

    audio_base64: str | None
    mime_type: str
    provider: str
    voice: str
    bytes_count: int = 0
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VoiceEngine:
    """Abstração de STT (áudio -> texto) e TTS (texto -> áudio PT-BR)."""

    DEFAULT_TTS_VOICE = "pt-BR-FranciscaNeural"
    DEFAULT_MACOS_VOICE = "Luciana"

    def __init__(
        self,
        tts_voice: str | None = None,
        allow_network_tts: bool | None = None,
    ) -> None:
        self.tts_voice = (
            tts_voice
            or os.environ.get("SUS_CIDADAO_TTS_VOICE", "").strip()
            or self.DEFAULT_TTS_VOICE
        )
        if allow_network_tts is None:
            env_flag = os.environ.get("SUS_CIDADAO_ENABLE_EDGE_TTS", "1").strip()
            self.allow_network_tts = env_flag != "0"
        else:
            self.allow_network_tts = allow_network_tts

    @staticmethod
    def stt_provider_configured() -> str | None:
        """Retorna o provedor de STT de servidor configurado via ambiente, se houver."""
        if os.environ.get("GEMINI_API_KEY", "").strip():
            return "gemini_audio"
        if os.environ.get("OPENAI_API_KEY", "").strip():
            return "openai_whisper"
        return None

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "voice.webm",
        mime_type: str = "audio/webm",
    ) -> STTResult:
        """Transcreve áudio enviado pelo app usando Gemini Audio ou OpenAI Whisper."""
        if not audio_bytes:
            return STTResult(
                text="",
                provider="none",
                error="Arquivo de áudio vazio recebido pelo servidor.",
            )

        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if gemini_key:
            return self._transcribe_with_gemini(
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                api_key=gemini_key,
            )

        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            return self._transcribe_with_openai(
                audio_bytes=audio_bytes,
                filename=filename,
                mime_type=mime_type,
                api_key=openai_key,
            )

        return STTResult(
            text="",
            provider="browser_speech_recommended",
            error=(
                "Nenhuma chave GEMINI_API_KEY ou OPENAI_API_KEY configurada no servidor "
                "para transcrição de arquivo de áudio. Envie o campo `text` ou use o "
                "microfone em tempo real na interface Web (/voice-demo)."
            ),
        )

    @staticmethod
    def _transcribe_with_gemini(
        audio_bytes: bytes, mime_type: str, api_key: str
    ) -> STTResult:
        model = os.environ.get("SUS_CIDADAO_STT_GEMINI_MODEL", "gemini-2.5-flash")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Transcreva fielmente em português do Brasil o que a pessoa falou "
                                "neste áudio sobre medicamentos, exames do SUS ou unidades de saúde. "
                                "Retorne somente o texto transcrito, sem comentários."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type or "audio/webm",
                                "data": encoded,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 400},
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, params={"key": api_key}, json=payload)
                resp.raise_for_status()
                data = resp.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if not text:
                return STTResult(
                    text="",
                    provider="gemini_audio",
                    error="Gemini não identificou fala audível no áudio enviado.",
                )
            return STTResult(text=text, provider="gemini_audio")
        except Exception as exc:  # pragma: no cover - rede externa
            return STTResult(
                text="",
                provider="gemini_audio",
                error=f"Falha na transcrição via Gemini Audio: {exc}",
            )

    @staticmethod
    def _transcribe_with_openai(
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        api_key: str,
    ) -> STTResult:
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {
            "file": (
                filename or "audio.webm",
                audio_bytes,
                mime_type or "audio/webm",
            )
        }
        data = {
            "model": os.environ.get("SUS_CIDADAO_STT_OPENAI_MODEL", "whisper-1"),
            "language": "pt",
        }
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(url, headers=headers, files=files, data=data)
                resp.raise_for_status()
                payload = resp.json()
            text = str(payload.get("text", "")).strip()
            if not text:
                return STTResult(
                    text="",
                    provider="openai_whisper",
                    error="Whisper não identificou fala no áudio enviado.",
                )
            return STTResult(text=text, provider="openai_whisper")
        except Exception as exc:  # pragma: no cover - rede externa
            return STTResult(
                text="",
                provider="openai_whisper",
                error=f"Falha na transcrição via OpenAI Whisper: {exc}",
            )

    async def async_synthesize_speech(
        self,
        text: str,
        voice: str | None = None,
    ) -> TTSResult:
        """Sintetiza áudio PT-BR de forma assíncrona (ideal para FastAPI)."""
        clean_text = text.strip()
        selected_voice = voice or self.tts_voice
        if not clean_text:
            return TTSResult(
                audio_base64=None,
                mime_type="text/plain",
                provider="none",
                voice=selected_voice,
                fallback_reason="Texto vazio para síntese de voz.",
            )

        edge_error: str | None = None
        if self.allow_network_tts:
            try:
                edge_tts: Any = importlib.import_module("edge_tts")
                communicate = edge_tts.Communicate(
                    text=clean_text,
                    voice=selected_voice,
                    connect_timeout=6,
                    receive_timeout=15,
                )
                audio_chunks: list[bytes] = []
                async for chunk in communicate.stream():
                    if chunk.get("type") == "audio":
                        chunk_data = chunk.get("data", b"")
                        if isinstance(chunk_data, (bytes, bytearray)):
                            audio_chunks.append(bytes(chunk_data))
                audio_bytes = b"".join(audio_chunks)
                if len(audio_bytes) > 512:
                    return TTSResult(
                        audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
                        mime_type="audio/mpeg",
                        provider="edge_tts",
                        voice=selected_voice,
                        bytes_count=len(audio_bytes),
                    )
                edge_error = "edge-tts retornou stream de áudio vazio."
            except Exception as exc:
                edge_error = f"edge-tts indisponível ({exc})"

        # Fallback offline: macOS /usr/bin/say (ignora saídas <= 8 KB que representam apenas cabeçalho)
        say_result = self._try_macos_say_tts(clean_text)
        if say_result is not None:
            return say_result

        reason = edge_error or "TTS neural de rede desabilitado neste ambiente"
        return TTSResult(
            audio_base64=None,
            mime_type="text/plain",
            provider="browser_speech_synthesis",
            voice="pt-BR",
            bytes_count=0,
            fallback_reason=f"{reason}; cliente utilizará síntese de voz nativa (Web Speech API).",
        )

    def _try_macos_say_tts(self, text: str) -> TTSResult | None:
        """Tenta síntese offline via macOS `say` quando gera mídia válida (> 8 KB)."""
        say_bin = shutil.which("say")
        if not say_bin:
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
                out_path = Path(tmp.name)
            try:
                proc = subprocess.run(
                    [
                        say_bin,
                        "-v",
                        self.DEFAULT_MACOS_VOICE,
                        "--data-format=aac",
                        "-o",
                        str(out_path),
                        text,
                    ],
                    check=False,
                    capture_output=True,
                    timeout=12,
                )
                if proc.returncode == 0 and out_path.exists():
                    data = out_path.read_bytes()
                    if len(data) > 8192:
                        return TTSResult(
                            audio_base64=base64.b64encode(data).decode("ascii"),
                            mime_type="audio/mp4",
                            provider="macos_say",
                            voice=self.DEFAULT_MACOS_VOICE,
                            bytes_count=len(data),
                        )
            finally:
                if out_path.exists():
                    out_path.unlink(missing_ok=True)
        except Exception:
            return None
        return None

    def synthesize_speech(
        self,
        text: str,
        voice: str | None = None,
    ) -> TTSResult:
        """Versão síncrona de `async_synthesize_speech` para uso em CLI e testes."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.async_synthesize_speech(text=text, voice=voice))
        # Caso já exista loop rodando, retorna fallback sem travar event loop
        say_result = self._try_macos_say_tts(text)
        if say_result is not None:
            return say_result
        return TTSResult(
            audio_base64=None,
            mime_type="text/plain",
            provider="browser_speech_synthesis",
            voice=voice or self.tts_voice,
            fallback_reason="Loop assíncrono ativo; use `await async_synthesize_speech(...)`.",
        )

