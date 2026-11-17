"""Guardrail Ético Inegociável: Bloqueio de Conduta Clínica, Anti-Injeção e Pré-Exames (Lei nº 12.842/2013)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sus_cidadao_ds.guardrails.security import Canal, inspecionar_entrada
from sus_cidadao_ds.retrieval.retrievers import normalize_pt_text


@dataclass(frozen=True)
class ClinicalCheckResult:
    """Resultado da inspeção do Guardrail Clínico."""

    is_blocked: bool
    reason: str
    has_red_flag_emergency: bool
    safe_response: str


_SUBST_TERAPEUTICO = (
    r"(?:remedio\w*|medicamento\w*|medicac\w*|comprimido\w*|capsula\w*|gota\w*|ampola\w*"
    r"|xarope\w*|pomada\w*|colirio\w*|antibiotic\w*|anti-?inflamatori\w*|analgesic\w*"
    r"|antidepressiv\w*|calmant\w*|vitamina\w*|suplemento\w*|cha\b|dose\w*|dosagem\b)"
)
_SINTOMA_OU_QUEIXA = (
    r"(?:dor(?:es)?|febre|gripe|resfriado|tosse|insonia|ansiedade|infeccao|inflamacao"
    r"|garganta|dente|cabeca|costas|enxaqueca|nausea\w*|vomito\w*|diarreia|alergia"
    r"|pressao|glicose|sintoma\w*)"
)
_FAMILIAR_TERCEIRO = (
    r"(?:filh[oa]|crianca|bebe|irmao|irma|mae|pai|avo\b|marido|esposa|vizinh[oa]"
    r"|parente|outra pessoa|alguem)"
)


def _normalizar_ascii(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "\n".join(" ".join(linha.split()) for linha in sem_acento.lower().splitlines())


def _clausulas(texto_normalizado: str) -> list[str]:
    brutas = re.split(r"[.?!;\n]+", texto_normalizado)
    limpas: list[str] = []
    for cl in brutas:
        limpa = " ".join(re.sub(r"[^a-z0-9/\-\s]", " ", cl).split())
        if limpa:
            limpas.append(limpa)
    return limpas


class ClinicalBlocker:
    """Detecta e bloqueia pedidos clínicos (Ato Médico), suspensão pré-exame e prompt injection."""

    _ADMINISTRATIVO_PERMITIDO: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b(?:que horas?|horario)(?: de| para)?(?= (?:eu )?(?:tomo|tomar)\b)"),
        re.compile(
            r"\besqueci(?=(?: a| as| o| os| minha| minhas| meu| meus){0,2} "
            r"(?:orientacoes|documentos?|receita)\b)"
        ),
    )

    _PATTERNS_PRESCRICAO: tuple[re.Pattern[str], ...] = (
        re.compile(
            rf"\b(?:o que|qual|quais|que)\b(?:\W+\w+){{0,6}}?\W+"
            rf"\b(?:tomar|tomo|dar|dou|usar|uso|aplicar|aplico|serve|funciona|e bom|melhor)\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:{_SUBST_TERAPEUTICO}|{_SINTOMA_OU_QUEIXA})\b"
        ),
        re.compile(
            rf"\b(?:{_SINTOMA_OU_QUEIXA})\b(?:\W+\w+){{0,8}}?\W+"
            rf"\b(?:o que|qual|que)\b(?:\W+\w+){{0,4}}?\W+"
            r"\b(?:tomar|tomo|dar|dou|usar|uso|tomaria)\b"
        ),
        re.compile(
            rf"\b(?:me|nos|pode|poderia)\b(?:\W+\w+){{0,3}}?\W+"
            rf"\b(?:indica\w*|receit\w*|prescrev\w*|passa\w*|recomenda\w*)\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:{_SUBST_TERAPEUTICO}|{_SINTOMA_OU_QUEIXA})\b"
        ),
        re.compile(
            r"\b(?:qual|que)\b(?:\W+\w+){0,2}?\W+"
            r"\b(?:antibiotic\w*|anti-?inflamatori\w*|analgesic\w*|antidepressiv\w*|calmant\w*)\b"
        ),
    )

    _PATTERNS_DOSAGEM: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:partir|parto|parta|quebrar|quebro|dividir|divido|cortar|corto|amassar|abrir"
            r"|dobrar|dobro|duplicar|triplicar|aumentar|aumento|diminuir|diminuo|reduzir|reduzo"
            r"|repetir|repito|parar|paro|suspender|suspendo|interromper)\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:{_SUBST_TERAPEUTICO}|ao meio|no meio|metade|tratamento)\b"
        ),
        re.compile(
            r"\b(?:quantos?|qual(?:\s+e)?|que)\b(?:\W+\w+){0,4}?\W+"
            r"\b(?:comprimido\w*|capsula\w*|gota\w*|dose\w*|dosagem|ml|mg)\b"
            r"(?:\W+\w+){0,6}?\W+\b(?:tomar|tomo|dar|dou|usar|uso|posso|devo|certa|ideal"
            r"|recomendad\w*|peso|kg|idade|crianca|adulto|por dia|ao dia)\b"
        ),
        re.compile(
            r"\b(?:tomar|tomei|tomo|usar|usei|dar|dei|tomaria)\b(?:\W+\w+){0,7}?\W+"
            r"\b(?:duas?\s+vezes|2\s*x|em\s+dobro|dobrad\w*|dois|duas|tres|a\s+mais|junto"
            r"|de\s+novo|novamente|atrasad\w*|ontem|de\s+uma\s+vez)\b"
        ),
        re.compile(
            r"\b(?:tomar|tomei|tomo|usar|usei|dar|dei|tomaria)\b(?:\W+\w+){0,4}?\W+"
            r"\b(?:\d+|dois|duas|tres)\s+(?:comprimido\w*|capsula\w*|gota\w*|dose\w*)\b"
            r"(?:\W+\w+){0,7}?\W+\b(?:de\s+uma\s+vez|junt[oa]s?|faz\s+mal|risco|perigo\w*"
            r"|problema|pode|posso|devo|hoje)\b"
        ),
        re.compile(
            r"\b(?:duas?\s+vezes|2\s*x|em\s+dobro|dobro|esqueci)\b(?:\W+\w+){0,7}?\W+"
            r"\b(?:tomo|tomar|comprimido|dose|remedio|faz\s+mal|problema|perigo\w*|hoje)\b"
        ),
        re.compile(
            r"\b(?:tomo|tomar|tomei|posso|devo|faz\s+mal|problema|perigo\w*)\b"
            r"(?:\W+\w+){0,4}?\W+\bmetade\b"
        ),
        re.compile(r"\bmetade\b(?:\W+\w+){0,5}?\W+\b(?:faz\s+mal|problema|perigo\w*|posso|devo)\b"),
    )

    _PATTERNS_DIAGNOSTICO: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:o que\s+(?:eu\s+)?tenho|sera\s+que\s+(?:eu\s+)?tenho"
            r"|pelos?\s+(?:meus?\s+)?sintomas?)\b"
        ),
        re.compile(
            r"(?<!nao )\b(?:eu\s+tenho|estou\s+com)\b"
            r"(?!\s+(?:historico|historia|antecedente)\b)(?:\W+\w+){0,5}?\W+"
            r"\b(?:diabetes|dengue|covid|doenca|alergia|infeccao|anemia|infarto|avc|grave)\b"
        ),
        re.compile(
            r"\b(?:meu\s+exame|exame\s+de|minha\s+glicose|minha\s+pressao|manchas?|caroco"
            r"|hemoglobina|resultado)\b(?:\W+\w+){0,7}?\W+"
            r"\b(?:e\s+grave|sao\s+alergia|e\s+alergia|diabetes|dengue|covid|doenca"
            r"|significa|indica)\b"
        ),
        re.compile(
            rf"\b(?:{_SINTOMA_OU_QUEIXA})\b(?:\W+\w+){{0,6}}?\W+"
            r"\b(?:e\s+(?:grave|alergia|dengue|covid|infarto|avc)|pode\s+ser\s+\w+)\b"
        ),
    )

    _PATTERNS_TROCA: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:trocar|troco|substitu\w*|alternativa|equivalente|no\s+lugar\s+(?:de|do|da)"
            r"|em\s+vez\s+(?:de|do|da))\b(?:\W+\w+){0,7}?\W+"
            rf"\b(?:{_SUBST_TERAPEUTICO}|exame|tratamento|medico|receita|marca|jejum)\b"
        ),
        re.compile(
            r"\b(?:posso|pode|devo|consigo|quero)\b(?:\W+\w+){0,3}?\W+"
            r"\b(?:trocar|substituir|mudar)\b(?:\W+\w+){0,6}?\W+\b(?:pelo|pela|por)\b"
            r"(?!\W+(?:receita|cadastro|endereco|unidade|ubs|horario|comprovante|documento|conta)\b)"
        ),
        re.compile(
            rf"\b(?:{_SUBST_TERAPEUTICO}|exame)\b(?:\W+\w+){{0,6}}?\W+"
            r"\b(?:substitui\w*|troca\w*|no\s+lugar|em\s+vez)\b"
        ),
        re.compile(
            rf"\b(?:{_FAMILIAR_TERCEIRO})\b(?:\W+\w+){{0,7}}?\W+"
            rf"\b(?:usar|tomar|dar|uso|tomo|dou)\b(?:\W+\w+){{0,6}}?\W+\b{_SUBST_TERAPEUTICO}\b"
        ),
        re.compile(
            rf"\b(?:usar|tomar|dar|uso|tomo|dou)\b(?:\W+\w+){{0,6}}?\W+\b{_SUBST_TERAPEUTICO}\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:do\s+{_FAMILIAR_TERCEIRO}|da\s+{_FAMILIAR_TERCEIRO}"
            r"|de\s+outra\s+pessoa|que\s+sobrou|parecido|o\s+que\s+eu\s+quiser)\b"
        ),
        re.compile(
            r"\b(?:sem\s+o\s+remedio|sem\s+remedio|acabou\s+(?:o|meu)\s+remedio"
            r"|enquanto\s+nao\s+chega|faltou\s+o\s+remedio)\b(?:\W+\w+){0,8}?\W+"
            r"\b(?:uso|usar|tomo|tomar|vitamina\w*|cha\b|suplemento\w*|outro)\b"
        ),
    )

    _PATTERNS_JAILBREAK: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:ignore|desconsidere|esqueca|anule)\b(?:\W+\w+){0,4}?\W+"
            r"\b(?:instruc\w*|regras?|limites?|filtros?|diretriz\w*)\b"
        ),
        re.compile(r"\b(?:finja|simule|atue)\b(?:\W+\w+){0,3}?\W+\b(?:que|ser|como)\b"),
        re.compile(r"\bpergunta\s+hipotetica\b"),
        re.compile(r"\bmodo\s+(?:desenvolvedor|dev|irrestrito|sem\s+filtro)\b"),
        re.compile(r"\bregras\s+desligadas\b"),
        re.compile(
            r"\b(?:sou|como)\b(?:\W+\w+){0,3}?\W+"
            r"\b(?:enfermeir\w*|medic\w*|farmaceutic\w*)\b(?:\W+\w+){0,6}?\W+"
            rf"\b(?:{_SUBST_TERAPEUTICO}|receit\w*|prescrev\w*|posologia)\b"
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
        "falta de ar",
        "pressao subiu",
        "18x11",
        "18x12",
        "desmaio",
        "infarto",
        "avc",
    )

    def _subclausulas_clinicas(self, texto: str) -> list[str]:
        for pattern in self._ADMINISTRATIVO_PERMITIDO:
            texto = pattern.sub(" ", texto)
        return _clausulas(texto)

    def _tem_emergencia_ativa(self, texto: str) -> bool:
        """Verifica se há emergência médica ativa, respeitando negação/histórico ligado ao sinal."""
        sinais = "|".join(re.escape(flag) for flag in self._EMERGENCY_RED_FLAGS)
        negacao = re.compile(
            r"\b(?:nao(?: (?:tenho|sinto|apresento|estou com|esta com|tem|ha))?"
            r"|sem|nega|negando|negativo para|ausencia de|nem) "
            rf"(?:(?:{sinais})\s+(?:e|nem|ou)\s+)*$"
        )
        historico = re.compile(
            r"\b(?:historico de|historia previa de|antecedente de|antecedentes de"
            r"|historia pregressa de|ja teve|teve|sofreu)(?: um| uma)? $"
        )
        for trecho in re.split(
            r"[.?!;,\n]+|\b(?:mas|porem|contudo|entretanto|todavia)\b", texto
        ):
            for ocorrencia in re.finditer(rf"\b(?:{sinais})\b", trecho):
                prefixo = trecho[: ocorrencia.start()]
                if not negacao.search(prefixo) and not historico.search(prefixo):
                    return True
        return False

    def inspect(self, query: str, canal: str = "texto") -> ClinicalCheckResult:
        """Verifica se a consulta viola o Ato Médico, preparo medicamentoso ou anti-injection."""
        check_injecao = inspecionar_entrada(query, Canal(canal) if canal in {"texto", "pdf", "voz"} else Canal.TEXTO)
        norm_pt = normalize_pt_text(query)
        norm_ascii = _normalizar_ascii(query)
        tokens = set(re.findall(r"[a-z0-9]+", norm_pt))
        has_emergency = self._tem_emergencia_ativa(norm_ascii)

        has_pre_exam_decision = (
            any(w in tokens for w in self._PRE_EXAM_ACTION_WORDS)
            and any(w in tokens for w in self._PRE_EXAM_DRUG_WORDS)
            and any(w in tokens for w in self._PRE_EXAM_CONTEXT_WORDS)
        )
        if has_pre_exam_decision:
            return ClinicalCheckResult(
                is_blocked=True,
                reason="SOLICITACAO_SUSPENSAO_MEDICAMENTO_PRE_EXAME",
                has_red_flag_emergency=has_emergency,
                safe_response=(
                    "BLOQUEIO ÉTICO E CLÍNICO (Preservação do Ato Médico — Lei nº 12.842/2013): "
                    "O SUS Cidadão orienta apenas o preparo logístico e administrativo de exames e não pode "
                    "decidir se você deve suspender, interromper ou tomar medicamentos contínuos (como insulina, "
                    "anti-hipertensivos, metformina ou anticoagulantes) antes do exame. "
                    "Confirme essa conduta diretamente com o médico solicitante ou com a unidade de saúde "
                    "onde o exame foi agendado antes da data do procedimento."
                ),
            )

        if has_emergency:
            return ClinicalCheckResult(
                is_blocked=True,
                reason="EMERGENCIA_MEDICA",
                has_red_flag_emergency=True,
                safe_response=(
                    "BLOQUEIO ÉTICO E CLÍNICO (Preservação do Ato Médico — Lei nº 12.842/2013): "
                    "ALERTA DE URGÊNCIA: Diante de sinais de alarme como dor no peito, falta de ar "
                    "ou picos pressóricos, procure imediatamente uma UPA 24h, acione o SAMU (192) ou "
                    "dirija-se ao serviço médico de emergência mais próximo. "
                    "O SUS Cidadão atua exclusivamente na navegação administrativa e não realiza "
                    "atendimento médico emergencial."
                ),
            )

        clausulas = self._subclausulas_clinicas(norm_ascii)
        regras = (
            ("PRESCRICAO", self._PATTERNS_PRESCRICAO),
            ("DOSAGEM", self._PATTERNS_DOSAGEM),
            ("DIAGNOSTICO", self._PATTERNS_DIAGNOSTICO),
            ("TROCA_TERAPEUTICA", self._PATTERNS_TROCA),
            ("JAILBREAK", self._PATTERNS_JAILBREAK),
        )
        for clausula in clausulas:
            for motivo, patterns in regras:
                if any(p.search(clausula) for p in patterns):
                    return ClinicalCheckResult(
                        is_blocked=True,
                        reason=motivo,
                        has_red_flag_emergency=False,
                        safe_response=(
                            "BLOQUEIO ÉTICO E CLÍNICO (Preservação do Ato Médico — Lei nº 12.842/2013): "
                            "O SUS Cidadão atua estritamente na orientação administrativa para acesso ao SUS "
                            "e não prescreve, diagnostica, suspende, fraciona ou substitui medicamentos. "
                            "Procure o médico da sua Equipe de Saúde da Família (eSF) na UBS de referência "
                            "para avaliação segura do seu tratamento."
                        ),
                    )

        if check_injecao.motivos and check_injecao.bloqueado:
            return ClinicalCheckResult(
                is_blocked=True,
                reason="PROMPT_INJECTION",
                has_red_flag_emergency=False,
                safe_response=(
                    "Aviso de Segurança (Preservação do Ato Médico — Lei nº 12.842/2013): "
                    "A solicitação contém instruções incompatíveis com o escopo de navegação "
                    "administrativa do SUS Cidadão. Informe apenas o nome do medicamento ou "
                    "exame prescrito para consultar as rotas oficiais de acesso gratuito."
                ),
            )

        return ClinicalCheckResult(
            is_blocked=False,
            reason="PERMITIDO",
            has_red_flag_emergency=False,
            safe_response="",
        )
