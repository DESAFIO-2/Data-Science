"""Mascaramento de Dados Pessoais Sensíveis (PII Masking — LGPD Art. 11) em receitas, textos e voz."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_TERMOS_NAO_PESSOA: frozenset[str] = frozenset(
    {
        "distrito federal",
        "farmacia popular",
        "alto custo",
        "atencao primaria",
        "sistema unico",
        "hospital dia",
        "asa sul",
        "asa norte",
        "taguatinga sul",
        "taguatinga norte",
        "ceilandia norte",
        "santa maria",
        "lago sul",
        "lago norte",
        "nucleo bandeirante",
        "riacho fundo",
        "sao sebastiao",
        "jardim botanico",
        "vicente pires",
        "sol nascente",
        "aguas claras",
        "sus cidadao",
        "sus df",
        "componente especializado",
    }
)


@dataclass(frozen=True)
class PIIMaskingResult:
    """Resultado auditável da desidentificação LGPD."""

    sanitized_text: str
    detected_pii_types: list[str]
    redaction_count: int


class PIIMasker:
    """Aplica desidentificação determinística preservando fármacos e localidades do DF."""

    _CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
    _CNS_PATTERN = re.compile(r"\b[12789]\d{2}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}\b")
    _RG_PATTERN = re.compile(r"(?i)\bRG[:\s#-]*\d{1,2}\.?\d{3}\.?\d{3}(?:-[\dX])?\b")
    _CRM_PATTERN = re.compile(r"(?i)\bCRM(?:[-/\s]*[A-Z]{2})?[:\s#-]*\d{4,7}\b")
    _CID10_PATTERN = re.compile(r"(?i)\bCID(?:-?10)?[:\s#-]*[A-TV-Z]\d{2}(?:\.\d{1,2})?\b")
    _CEP_PATTERN = re.compile(r"(?i)(?:\bCEP[:\s#-]*)?\b\d{2}\.?\d{3}-\d{3}\b")
    _ADDRESS_PATTERN = re.compile(
        r"(?i)\b(?:endere[cç]o\s*:\s*[^\n;]{4,80}"
        r"|(?:quadra|qnm|qnn|qno|qnj|qnl|qs|csb|cnb|sqs|sqn|shis|shin|cln|cls"
        r"|rua|avenida|av\.?)\s+[A-Za-zÀ-Ú0-9][^\n,;]{2,45})"
    )
    _PHONE_PATTERN = re.compile(
        r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-\s]?\d{4}\b"
    )
    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _PATIENT_NAME_PATTERN = re.compile(
        r"(?i)\b(paciente|nome\s+do\s+paciente|titular)\s*:\s*"
        r"([A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+){1,4})"
    )
    _FREE_NAME_PATTERN = re.compile(
        r"\b(?P<prefixo>(?i:meu nome [eé]|me chamo|chamo-me|para [oa]|dona|sr\.?|sra\.?)\s+)"
        r"(?P<nome>[A-ZÀ-Ú][a-zà-ú]{1,20}"
        r"(?:\s+(?:da|de|do|dos|das|[A-ZÀ-Ú][a-zà-ú]{1,20})){1,3})\b"
    )

    def _substituir_nome_livre(self, match: re.Match[str], cont: list[int]) -> str:
        nome = match.group("nome")
        nome_ascii = (
            unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
        )
        if nome_ascii in _TERMOS_NAO_PESSOA:
            return match.group(0)
        cont[0] += 1
        return f"{match.group('prefixo')}[PACIENTE_DESIDENTIFICADO_LGPD]"

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

        livres = [0]
        candidato = self._FREE_NAME_PATTERN.sub(
            lambda m: self._substituir_nome_livre(m, livres), sanitized
        )
        if livres[0] > 0:
            sanitized = candidato
            redactions += livres[0]
            if "PATIENT_NAME" not in detected_types:
                detected_types.append("PATIENT_NAME")

        patterns: tuple[tuple[re.Pattern[str], str, str], ...] = (
            (self._CNS_PATTERN, "[CNS_MASCARADO_LGPD]", "CNS_CARTAO_SUS"),
            (self._CPF_PATTERN, "[CPF_MASCARADO_LGPD]", "CPF"),
            (self._RG_PATTERN, "[RG_MASCARADO_LGPD]", "RG"),
            (self._CRM_PATTERN, "[CRM_MASCARADO_LGPD]", "CRM"),
            (self._CID10_PATTERN, "[CID_MASCARADO_LGPD]", "CID10"),
            (self._CEP_PATTERN, "[CEP_MASCARADO_LGPD]", "CEP"),
            (self._ADDRESS_PATTERN, "[ENDERECO_MASCARADO_LGPD]", "ADDRESS"),
            (self._EMAIL_PATTERN, "[EMAIL_MASCARADO_LGPD]", "EMAIL"),
            (self._PHONE_PATTERN, "[TELEFONE_MASCARADO_LGPD]", "PHONE"),
        )
        for regex, placeholder, pii_type in patterns:
            if regex.search(sanitized):
                sanitized, count = regex.subn(placeholder, sanitized)
                redactions += count
                detected_types.append(pii_type)

        return PIIMaskingResult(
            sanitized_text=sanitized,
            detected_pii_types=detected_types,
            redaction_count=redactions,
        )

    mascarar = mask
