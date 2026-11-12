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
    """Detecta e bloqueia pedidos de diagnóstico, ajuste de dose, troca ou suspensão de medicamentos."""

    _DOSE_CHANGE_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b(posso|devo|preciso)\s+(dobrar|aumentar|diminuir|parar|suspender|interromper|cortar)\b"),
        re.compile(r"\b(dobrar|aumentar|reduzir)\s+a?\s*dose\b"),
        re.compile(r"\btrocar\s+(por|pelo|pela)\b"),
        re.compile(r"\bqual\s+(outro|remedio|medicamento|antidepressivo)\s+.*\b(receita|substituir|tomar)\b"),
        re.compile(r"\b(substituir|tomar)\s+sem\s+receita\b"),
        re.compile(r"\bme\s+(receita|indica|prescreve)\s+um\b"),
    )

    _PRE_EXAM_MED_DECISION_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(parar|suspender|interromper|manter|continuar|tomo|tomar)\b.*\b"
            r"(remedio|medicamento|insulina|anticoagulante|aas|metformina|losartana|pressao)\b.*"
            r"\b(exame|jejum|endoscopia|ressonancia|cirurgia|coleta)\b"
        ),
        re.compile(
            r"\b(remedio|medicamento|insulina|anticoagulante|aas|metformina|losartana|pressao)\b.*"
            r"\b(antes do exame|no dia do exame|em jejum|paro ou tomo|tomo ou paro)\b"
        ),
    )

    _PRE_EXAM_ACTION_WORDS: tuple[str, ...] = (
        "parar",
        "paro",
        "suspender",
        "suspendo",
        "interromper",
        "manter",
        "continuar",
        "tomo",
        "tomar",
    )
    _PRE_EXAM_DRUG_WORDS: tuple[str, ...] = (
        "remedio",
        "remedios",
        "medicamento",
        "medicamentos",
        "medicacao",
        "insulina",
        "anticoagulante",
        "marevan",
        "varfarina",
        "aas",
        "metformina",
        "losartana",
        "pressao",
        "comprimido",
    )
    _PRE_EXAM_CONTEXT_WORDS: tuple[str, ...] = (
        "exame",
        "exames",
        "jejum",
        "endoscopia",
        "ressonancia",
        "tomografia",
        "ultrassom",
        "ecocardiograma",
        "coleta",
        "cirurgia",
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
        tokens = set(re.findall(r"[a-z0-9]+", norm))
        has_emergency = any(flag in norm for flag in self._EMERGENCY_RED_FLAGS)

        has_pre_exam_decision = any(p.search(norm) for p in self._PRE_EXAM_MED_DECISION_PATTERNS) or (
            any(w in tokens for w in self._PRE_EXAM_ACTION_WORDS)
            and any(w in tokens for w in self._PRE_EXAM_DRUG_WORDS)
            and any(w in tokens for w in self._PRE_EXAM_CONTEXT_WORDS)
        )

        if has_pre_exam_decision:
            msg = (
                "BLOQUEIO ÉTICO E CLÍNICO (Preservação do Ato Médico — Lei nº 12.842/2013): "
                "O SUS Cidadão orienta apenas o preparo logístico e administrativo de exames e não pode "
                "decidir se você deve suspender, interromper ou tomar medicamentos contínuos (como insulina, "
                "anti-hipertensivos, metformina ou anticoagulantes) antes do exame. "
                "Confirme essa conduta diretamente com o médico solicitante ou com a unidade de saúde "
                "onde o exame foi agendado antes da data do procedimento."
            )
            return ClinicalCheckResult(
                is_blocked=True,
                reason="SOLICITACAO_SUSPENSAO_MEDICAMENTO_PRE_EXAME",
                has_red_flag_emergency=has_emergency,
                safe_response=msg,
            )

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

