"""Esteira de segurança anti-injection, desobfuscação Unicode e validação de saída (OWASP LLM Top 10).

Replicada diretamente de `DESAFIO-2/development/backend/app/seguranca/`.
"""

from __future__ import annotations

import base64
import binascii
import html
import logging
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger("sus_cidadao_ds.seguranca")

MAX_CARACTERES: dict[str, int] = {"texto": 2_000, "pdf": 20_000, "voz": 2_000}

_ESPACOS = re.compile(r"\s+")
_LETRAS_ESPACADAS = re.compile(r"\b(?:\w[\s.\-_*]){3,}\w\b")
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_P = re.compile
_BASE64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


class Canal(StrEnum):
    """Canal multimodal de entrada do usuário."""

    TEXTO = "texto"
    PDF = "pdf"
    VOZ = "voz"


def contar_invisiveis(texto: str) -> int:
    """Conta caracteres invisíveis (zero-width, bidi, BOM: categoria Unicode Cf)."""
    return sum(1 for caractere in texto if unicodedata.category(caractere) == "Cf")


def limpar_texto_seguro(texto: str) -> str:
    """Normaliza via NFKC, remove caracteres invisíveis e colapsa espaços."""
    normalizado = unicodedata.normalize("NFKC", texto)
    sem_invisiveis = "".join(c for c in normalizado if unicodedata.category(c) != "Cf")
    return _ESPACOS.sub(" ", sem_invisiveis).strip()


def forma_de_comparacao(texto: str) -> str:
    """Gera representação normalizada para detecção anti-ofuscação (minúscula, sem leet/espaços)."""
    base = limpar_texto_seguro(texto).lower()
    sem_acento = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    sem_leet = sem_acento.translate(_LEET)
    return _LETRAS_ESPACADAS.sub(lambda m: re.sub(r"[\s.\-_*]", "", m.group()), sem_leet)


FORTES: dict[str, tuple[re.Pattern[str], ...]] = {
    "IGNORAR_INSTRUCOES": (
        _P(
            r"\b(ignor\w*|desconsider\w*|esquec(a|am|e|er)|descart\w*|desobedec\w*|anul\w*"
            r"|contorn\w*|burl\w*|pul(a|e|am|ar)"
            r"|nao (siga|seguir|obedeca|obedecer|respeite|respeitar|cumpra|cumprir))\b"
            r"(\W+\w+){0,4}?\W+(instruc\w*|regras?|orientac\w*|diretriz\w*|comandos?"
            r"|prompts?|restric\w*|politicas?|limites?|filtros?|travas?)"
        ),
        _P(
            r"\b(ignor\w*|desconsider\w*|esquec(a|am|e|er)|apag\w*)\b\W+(tudo|todas?|todos?)\b"
            r"(\W+\w+){0,2}?\W+(te|lhe|foi|voce) (\w+ )?(falad\w*|falaram|disseram|dito"
            r"|mandaram|mandad\w*|ensin\w*|instru\w*|program\w*|pediram|configur\w*)"
        ),
        _P(r"\b(ignore|disregard|forget)\b\W+(everything|all)\W+(above|before|previous)"),
        _P(
            r"\b(ignore|disregard|forget|override|bypass)\b(\W+\w+){0,4}?\W+"
            r"(instructions?|rules?|prompts?|guidelines?|restrictions?)"
        ),
    ),
    "TROCA_DE_PAPEL": (
        _P(
            r"\b(finja|fingir|finge|simule|atue|aja|comporte-se)\b(\W+\w+){0,3}?\W+(como|que|ser)\b"
        ),
        _P(r"\b(a partir de agora|de agora em diante)\b(\W+\w+){0,3}?\W+(voce|vc)\b"),
        _P(r"\b(voce|vc) (agora )?(e|sera|vai ser) (um|uma|o|a) (\w+ )?(medic|farmaceutic|ia sem)"),
        _P(r"\b(pretend|act as|you are now|roleplay)\b"),
        _P(r"\bmodo (desenvolvedor|dev|deus|irrestrito|sem (filtro|censura|regras?))\b"),
        _P(r"\b(jailbreak|dan mode|do anything now)\b"),
    ),
    "VAZAMENTO_DE_PROMPT": (
        _P(
            r"\b(mostre|mostra|revele|revela|repita|repete|imprima|escreva|diga|liste|copie)\b"
            r"(\W+\w+){0,6}?\W+(prompt|instrucoes (do sistema|iniciais|originais|internas)"
            r"|regras internas|configuracao interna)"
        ),
        _P(
            r"\b(quais|qual|como) (sao|e|foram) (as |o |os )?(suas|tuas|seu|teu|seus|teus) "
            r"(regras|instrucoes|prompt|diretrizes|ordens|configurac\w*)"
        ),
        _P(r"\b(system prompt|reveal (your|the) (instructions|prompt))\b"),
    ),
    "DELIMITADOR_FALSO": (
        _P(r"<\|?\s*(im_start|im_end|system|endoftext)\s*\|?>"),
        _P(r"\[/?(inst|sys)\]|<</?sys>>"),
        _P(r"(^|\W)(#{2,}|-{3,})\s*(system|sistema|instrucoes?)\b"),
        _P(r"\b(role|papel)\s*[:=]\s*(system|sistema)\b"),
        _P(r"(^|[.?!:]\s*)(system|sistema|assistant|assistente)\s*:"),
        _P(r"</?\s*(\w+_nao_confiavel|system|instructions)\s*>"),
    ),
}

FRACOS: dict[str, tuple[re.Pattern[str], ...]] = {
    "AUTORIDADE_ALEGADA": (
        _P(
            r"\b(sou|como) (o |a |um |uma )?(medic\w*|enfermeir\w*|farmaceutic\w*"
            r"|administrador\w*|admin|desenvolvedor\w*|programador\w*|da equipe|do suporte"
            r"|seu criador)"
        ),
        _P(
            r"\b(liberado|autorizado|permitido|aprovado) (pelo|pela|por) (o |a )?"
            r"(admin\w*|medic\w*|desenvolvedor\w*|equipe|suporte)"
        ),
        _P(r"\b(i am|i'm) (a |the )?(doctor|nurse|admin|developer)\b"),
    ),
    "PEDIDO_DE_LIBERACAO": (
        _P(
            r"\b(liber\w*|desbloque\w*|desativ\w*|deslig\w*|autoriz\w*|permit\w*)\b(\W+\w+){0,4}?"
            r"\W+(posologia|dose|dosagem|resposta completa|filtro|guardrail|seguranca|restric\w*"
            r"|trava\w*|bloqueio\w*|protec\w*)"
        ),
        _P(r"\bsem (filtro|censura|restric\w*|limites?)\b"),
        _P(
            r"\b(pode|podes|consegue|poderia)\b (me )?(passar|falar|dizer|informar|dar)\b"
            r"(\W+\w+){0,2}?\W+(posologia|dose|dosagem)"
        ),
    ),
    "EXFILTRACAO": (
        _P(
            r"\b(envie|mande|encaminhe|poste|acesse)\b[^.!?]{0,80}?\b"
            r"(https?|url|link|webhook|e-?mail)"
        ),
        _P(r"!\[[^\]]*\]\(https?://"),
    ),
    "OFUSCACAO": (_P(r"[a-z0-9+/]{40,}={0,2}"),),
}


@dataclass(frozen=True)
class ResultadoInjecao:
    """Decisão auditável do detector de prompt injection (sem vazar conteúdo)."""

    bloqueado: bool
    motivos: tuple[str, ...]


def _familias(texto: str, familias: dict[str, tuple[re.Pattern[str], ...]]) -> list[str]:
    return [nome for nome, padroes in familias.items() if any(p.search(texto) for p in padroes)]


def _decodificar_base64(texto: str) -> str:
    decodificados: list[str] = []
    for bloco in _BASE64.findall(texto):
        try:
            decodificados.append(base64.b64decode(bloco, validate=True).decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError):
            continue
    return " ".join(decodificados)


def detectar_injecao(texto: str) -> ResultadoInjecao:
    """Executa detecção anti-injection sobre texto, Base64 embutido e Unicode invisível."""
    comparavel = forma_de_comparacao(f"{texto} {_decodificar_base64(texto)}")
    fortes = _familias(comparavel, FORTES)
    fracos = _familias(comparavel, FRACOS)
    if contar_invisiveis(texto) > 0:
        fracos.append("CARACTERES_INVISIVEIS")
    bloqueado = bool(fortes) or len(fracos) >= 2
    return ResultadoInjecao(bloqueado=bloqueado, motivos=tuple(fortes + fracos))


def inspecionar_entrada(texto: str, canal: Canal | str = Canal.TEXTO) -> ResultadoInjecao:
    """Valida tamanho máximo por canal e aplica detecção determinística de injection."""
    canal_key = str(canal).lower()
    max_len = MAX_CARACTERES.get(canal_key, 2_000)
    if len(texto) > max_len:
        resultado = ResultadoInjecao(bloqueado=True, motivos=("TEXTO_GRANDE_DEMAIS",))
    else:
        resultado = detectar_injecao(texto)
    logger.info(
        "decisao_anti_injection canal=%s bloqueado=%s motivos=%s",
        canal_key,
        resultado.bloqueado,
        list(resultado.motivos),
    )
    return resultado


def delimitar_nao_confiavel(texto: str, canal: Canal | str = Canal.TEXTO) -> str:
    """Envolve texto externo (PDF/voz) escapado contra injeção em prompts LLM."""
    seguro = html.escape(limpar_texto_seguro(texto), quote=True)
    return f'<documento_nao_confiavel origem="{canal}">\n{seguro}\n</documento_nao_confiavel>'


# ---------------------------------------------------------------------------
# Validação determinística de saída (OWASP LLM02 / LLM05 / LLM09)
# ---------------------------------------------------------------------------
_ACAO_SAIDA = (
    r"\b(?:dobr|aument|diminu|reduz|suspend|interromp|substitu|troc|troqu"
    r"|part|quebr|divid|cort|compartilh|emprest)\w*"
)
_ALVO_SAIDA = (
    r"(?:a dose|as doses|a dosagem|o remedio|os remedios|o medicamento|os medicamentos"
    r"|a medicacao|o comprimido|os comprimidos|a capsula|as capsulas|o xarope)"
)
_POSOLOGIA_SAIDA = re.compile(
    rf"{_ACAO_SAIDA}(?:\W+\w+){{0,3}}?\W+{_ALVO_SAIDA}"
    r"|\bde \d+ em \d+ ?h(?:oras)?\b"
    r"|\ba cada \d+ ?h(?:oras)?\b"
    r"|\b\d+ ?(?:x|vezes) (?:ao|por) dia\b"
    r"|\btom[ea]r? \d+ (?:comprimidos?|capsulas?|gotas|doses?)\b"
)
_FRONTEIRA_CLAUSULA = re.compile(r"(?:[.;!?]|\b(?:mas|porem|contudo|entretanto|todavia)\b)")
_NEGACAO_SAIDA = re.compile(r"\b(?:nao|nunca|jamais|evite|sem orientacao|sem falar)\b[^.;!?]{0,40}$")
_CITACAO_DOCUMENTO = re.compile(r"fonte\s*:\s*([^|\]\n;]+?)\s*\|", re.IGNORECASE)


@dataclass(frozen=True)
class ResultadoSaida:
    """Resultado da validação determinística da resposta final ao cidadão."""

    aprovada: bool
    motivos: tuple[str, ...]


def _orienta_posologia(texto: str) -> bool:
    forma = unicodedata.normalize("NFKD", limpar_texto_seguro(texto).lower()).encode("ascii", "ignore").decode()
    for achado in _POSOLOGIA_SAIDA.finditer(forma):
        prefixo = forma[: achado.start()]
        ultimo_corte = 0
        for fronteira in _FRONTEIRA_CLAUSULA.finditer(prefixo):
            ultimo_corte = fronteira.end()
        clausula_anterior = prefixo[ultimo_corte:]
        if not _NEGACAO_SAIDA.search(clausula_anterior):
            return True
    return False


def validar_saida(
    texto: str,
    ids_contexto: Collection[str] = (),
    detected_pii_types: Collection[str] = (),
) -> ResultadoSaida:
    """Verifica se a resposta não vaza PII, posologia clínica nem citação inventada."""
    motivos = [f"PII_{tipo}" for tipo in detected_pii_types]
    if _orienta_posologia(texto):
        motivos.append("ORIENTACAO_POSOLOGIA_OU_TROCA")
    if ids_contexto:
        permitidos = set(ids_contexto)
        citados = (m.group(1).strip() for m in _CITACAO_DOCUMENTO.finditer(limpar_texto_seguro(texto)))
        if any(cid not in permitidos for cid in citados):
            motivos.append("CITACAO_FORA_DO_CONTEXTO")
    return ResultadoSaida(aprovada=not motivos, motivos=tuple(motivos))


EXTENSOES_ARQUIVO_PERMITIDAS: frozenset[str] = frozenset(
    {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".webm", ".m4a", ".wav", ".ogg", ".mp3"}
)
TAMANHO_MAXIMO_ARQUIVO_BYTES: int = 10 * 1024 * 1024


def validar_arquivo_entrada(
    nome_arquivo: str,
    tamanho_bytes: int,
    texto_extraido: str = "",
    canal: Canal | str = Canal.PDF,
) -> ResultadoInjecao:
    """Valida extensão, tamanho e conteúdo extraído de anexo PDF/áudio (preparo Semana 5)."""
    ext = Path(nome_arquivo or "").suffix.lower()
    if ext and ext not in EXTENSOES_ARQUIVO_PERMITIDAS:
        return ResultadoInjecao(bloqueado=True, motivos=("EXTENSAO_NAO_PERMITIDA",))
    if tamanho_bytes < 0 or tamanho_bytes > TAMANHO_MAXIMO_ARQUIVO_BYTES:
        return ResultadoInjecao(bloqueado=True, motivos=("ARQUIVO_EXCEDE_LIMITE",))
    if texto_extraido:
        return inspecionar_entrada(texto_extraido, canal=canal)
    return ResultadoInjecao(bloqueado=False, motivos=())


