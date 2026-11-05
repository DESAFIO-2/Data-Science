"""Mascaramento de Dados Pessoais Sensíveis (PII Masking — LGPD Art. 11) em receitas e áudios."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIMaskingResult:
    """Resultado auditável da desidentificação LGPD."""

    sanitized_text: str
    detected_pii_types: list[str]
    redaction_count: int


class PIIMasker:
    """Desidentifica CPF, Cartão SUS (CNS), telefone, e-mail e nome do paciente."""

    _CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
    _CNS_PATTERN = re.compile(r"\b[12789]\d{2}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}\b")
    _PHONE_PATTERN = re.compile(
        r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-\s]?\d{4}\b"
    )
    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _PATIENT_NAME_PATTERN = re.compile(
        r"(?i)\b(paciente|nome\s+do\s+paciente|titular)\s*:\s*([A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+){1,4})"
    )

    def mask(self, text: str) -> PIIMaskingResult:
        """Aplica mascaramento determinístico preservando entidades farmacêuticas e RAs."""
        sanitized = text
        detected_types: list[str] = []
        redactions = 0

        if self._PATIENT_NAME_PATTERN.search(sanitized):
            sanitized, count = self._PATIENT_NAME_PATTERN.subn(
                r"\1: [PACIENTE_DESIDENTIFICADO_LGPD]", sanitized
            )
            redactions += count
            detected_types.append("PATIENT_NAME")

        if self._CNS_PATTERN.search(sanitized):
            sanitized, count = self._CNS_PATTERN.subn("[CNS_MASCARADO_LGPD]", sanitized)
            redactions += count
            detected_types.append("CNS_CARTAO_SUS")

        if self._CPF_PATTERN.search(sanitized):
            sanitized, count = self._CPF_PATTERN.subn("[CPF_MASCARADO_LGPD]", sanitized)
            redactions += count
            detected_types.append("CPF")

        if self._EMAIL_PATTERN.search(sanitized):
            sanitized, count = self._EMAIL_PATTERN.subn(
                "[EMAIL_MASCARADO_LGPD]", sanitized
            )
            redactions += count
            detected_types.append("EMAIL")

        if self._PHONE_PATTERN.search(sanitized):
            sanitized, count = self._PHONE_PATTERN.subn(
                "[TELEFONE_MASCARADO_LGPD]", sanitized
            )
            redactions += count
            detected_types.append("PHONE")

        return PIIMaskingResult(
            sanitized_text=sanitized,
            detected_pii_types=detected_types,
            redaction_count=redactions,
        )

