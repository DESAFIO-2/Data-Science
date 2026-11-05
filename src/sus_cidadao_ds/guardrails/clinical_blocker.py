"""Guardrail Ético Inegociável: Bloqueio de Conduta Clínica e Preservação do Ato Médico."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sus_cidadao_ds.retrieval.retrievers import normalize_pt_text


@dataclass(frozen=True)
class ClinicalCheckResult:
    """Resultado da inspeção do Guardrail Clínico."""

    is_blocked: bool
    reason: str
    has_red_flag_emergency: bool
    safe_response: str


class ClinicalBlocker:
    """Detecta e bloqueia pedidos de diagnóstico, ajuste de dose ou troca de medicamentos."""

    _DOSE_CHANGE_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b(posso|devo)\s+(dobrar|aumentar|diminuir|parar|suspender|cortar)\b"),
        re.compile(r"\b(dobrar|aumentar|reduzir)\s+a?\s*dose\b"),
        re.compile(r"\btrocar\s+(por|pelo|pela)\b"),
        re.compile(r"\bqual\s+(outro|remedio|medicamento|antidepressivo)\s+.*\b(receita|substituir|tomar)\b"),
        re.compile(r"\b(substituir|tomar)\s+sem\s+receita\b"),
        re.compile(r"\bme\s+(receita|indica|prescreve)\s+um\b"),
    )

    _EMERGENCY_RED_FLAGS: tuple[str, ...] = (
        "dor no peito",
        "falta de ar grave",
        "pressao subiu",
        "18x11",
        "18x12",
        "desmaio",
        "infarto",
        "avc",
    )

    def inspect(self, query: str) -> ClinicalCheckResult:
        """Verifica se a consulta viola o limite de navegação administrativa."""
        norm = normalize_pt_text(query)
        has_emergency = any(flag in norm for flag in self._EMERGENCY_RED_FLAGS)

        for pattern in self._DOSE_CHANGE_PATTERNS:
            if pattern.search(norm):
                if has_emergency:
                    msg = (
                        "BLOQUEIO ÉTICO E CLÍNICO (Preservação do Ato Médico — Lei nº 12.842/2013): "
                        "O SUS Cidadão atua exclusivamente na navegação administrativa e não realiza "
                        "diagnóstico, ajuste de dosagem ou substituição de medicamentos. "
                        "ALERTA DE URGÊNCIA: Diante de sinais de alarme como pressão muito elevada ou "
                        "dor no peito, procure imediatamente uma UPA 24h, acione o SAMU (192) ou "
                        "dirija-se ao serviço médico de emergência mais próximo."
                    )
                else:
                    msg = (
                        "BLOQUEIO ÉTICO E CLÍNICO (Preservação do Ato Médico — Lei nº 12.842/2013): "
                        "O SUS Cidadão atua estritamente na orientação administrativa para acesso ao SUS "
                        "e não prescreve, suspende, altera dosagens ou substitui medicamentos. "
                        "Procure o médico da sua Equipe de Saúde da Família (eSF) na UBS de referência "
                        "para reavaliação segura do seu tratamento."
                    )
                return ClinicalCheckResult(
                    is_blocked=True,
                    reason="SOLICITACAO_CONDUTA_CLINICA_OU_TROCA_TERAPEUTICA",
                    has_red_flag_emergency=has_emergency,
                    safe_response=msg,
                )

        return ClinicalCheckResult(
            is_blocked=False,
            reason="NAVEGACAO_ADMINISTRATIVA_PERMITIDA",
            has_red_flag_emergency=False,
            safe_response="",
        )

