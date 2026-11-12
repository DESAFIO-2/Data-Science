"""Persistência de Memória Conversacional por Sessão com Conformidade LGPD.

Armazena exclusivamente contexto já sanitizado (RA detectada, medicamentos/exames
identificados e histórico mascarado) em SQLite local (`data/sessions/citizen_sessions.db`),
permitindo conversas multi-turno contínuas entre chamadas da API ou da CLI sem armazenar PII.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sus_cidadao_ds.core.config import ProjectPaths


@dataclass
class SessionContext:
    """Contexto persistente sanitizado de uma sessão do cidadão."""

    session_id: str
    detected_ra: str = "Distrito Federal (Geral)"
    known_medications: list[str] = field(default_factory=list)
    known_exams: list[str] = field(default_factory=list)
    sanitized_history: list[str] = field(default_factory=list)
    turn_count: int = 0
    updated_at_utc: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SQLiteSessionStore:
    """Repositório SQLite leve para persistência de sessões multi-turno do LangGraph."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            paths = ProjectPaths.from_root()
            self.db_path = paths.data_dir / "sessions" / "citizen_sessions.db"
        else:
            self.db_path = db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS citizen_sessions (
                    session_id TEXT PRIMARY KEY,
                    detected_ra TEXT NOT NULL,
                    known_medications_json TEXT NOT NULL,
                    known_exams_json TEXT NOT NULL,
                    sanitized_history_json TEXT NOT NULL,
                    turn_count INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def load_session(self, session_id: str) -> SessionContext:
        """Carrega uma sessão existente ou devolve um contexto inicial limpo."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, detected_ra, known_medications_json,
                       known_exams_json, sanitized_history_json, turn_count, updated_at_utc
                FROM citizen_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return SessionContext(session_id=session_id)

        return SessionContext(
            session_id=str(row[0]),
            detected_ra=str(row[1]),
            known_medications=list(json.loads(str(row[2]))),
            known_exams=list(json.loads(str(row[3]))),
            sanitized_history=list(json.loads(str(row[4]))),
            turn_count=int(row[5]),
            updated_at_utc=str(row[6]),
        )

    def save_session(self, context: SessionContext) -> None:
        """Persiste ou atualiza o contexto sanitizado da sessão em SQLite."""
        updated_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO citizen_sessions (
                    session_id, detected_ra, known_medications_json,
                    known_exams_json, sanitized_history_json, turn_count, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    detected_ra = excluded.detected_ra,
                    known_medications_json = excluded.known_medications_json,
                    known_exams_json = excluded.known_exams_json,
                    sanitized_history_json = excluded.sanitized_history_json,
                    turn_count = excluded.turn_count,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    context.session_id,
                    context.detected_ra,
                    json.dumps(context.known_medications, ensure_ascii=False),
                    json.dumps(context.known_exams, ensure_ascii=False),
                    json.dumps(context.sanitized_history, ensure_ascii=False),
                    context.turn_count,
                    updated_at,
                ),
            )
            conn.commit()

    def clear_session(self, session_id: str) -> None:
        """Remove uma sessão específica do armazenamento persistente."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM citizen_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

    def list_sessions(self) -> list[str]:
        """Lista os IDs das sessões armazenadas em ordem de atualização."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id FROM citizen_sessions ORDER BY updated_at_utc DESC"
            ).fetchall()
        return [str(r[0]) for r in rows]
