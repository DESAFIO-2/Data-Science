"""Rastreador leve de experimentos e linhagem em JSON puro (sem dependência do MLflow).

Registra parâmetros, métricas de avaliação (IR / RAGAS / calibração), tags de linhagem
(hashes SHA-256) e artefatos opcionais em `evals/reports/experiment_runs_registry.json`.
Projetado para execução determinística via CLI, CI/CD e DAGs do Apache Airflow.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ExperimentRunRecord:
    """Registro estruturado de uma execução experimental."""

    run_id: str
    experiment_name: str
    run_name: str
    timestamp_utc: str
    params: dict[str, str | int | float | bool] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)


class ExperimentTracker:
    """Gerenciador leve de rastreamento experimental baseado em JSON."""

    def __init__(
        self,
        registry_path: Path,
        artifacts_dir: Path | None = None,
        experiment_name: str = "sus_cidadao_rag_benchmarks",
    ) -> None:
        self.registry_path = registry_path
        self.artifacts_dir = artifacts_dir
        self.experiment_name = experiment_name

    def log_experiment_run(
        self,
        run_name: str,
        params: dict[str, str | int | float | bool],
        metrics: dict[str, float],
        tags: dict[str, str] | None = None,
        artifact_files: dict[str, Any] | None = None,
    ) -> ExperimentRunRecord:
        """Registra parâmetros, métricas, tags de linhagem e artefatos no registro JSON."""
        run_id = uuid.uuid4().hex
        timestamp_utc = datetime.now(UTC).isoformat()

        merged_tags: dict[str, str] = {
            "run_name": run_name,
            "project": "SUS_Cidadao_NavegaSUS",
            "methodology": "SDD",
        }
        if tags:
            merged_tags.update(tags)

        saved_artifacts: list[str] = []
        if artifact_files:
            if self.artifacts_dir is not None:
                run_artifacts_dir = self.artifacts_dir / run_id
                run_artifacts_dir.mkdir(parents=True, exist_ok=True)
                for filename, content in artifact_files.items():
                    target = run_artifacts_dir / filename
                    if isinstance(content, (dict, list)):
                        target.write_text(
                            json.dumps(content, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    else:
                        target.write_text(str(content), encoding="utf-8")
                    saved_artifacts.append(filename)
            else:
                saved_artifacts.extend(artifact_files.keys())

        record = ExperimentRunRecord(
            run_id=run_id,
            experiment_name=self.experiment_name,
            run_name=run_name,
            timestamp_utc=timestamp_utc,
            params=params,
            metrics={k: round(float(v), 6) for k, v in metrics.items()},
            tags=merged_tags,
            artifacts=saved_artifacts,
        )
        self._append_to_registry(record)
        return record

    def _append_to_registry(self, record: ExperimentRunRecord) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, Any]] = []
        if self.registry_path.exists():
            try:
                existing = json.loads(
                    self.registry_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                existing = []
        existing.append(asdict(record))
        self.registry_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_runs(self) -> list[ExperimentRunRecord]:
        """Retorna todas as execuções registradas no histórico."""
        if not self.registry_path.exists():
            return []
        raw_list: list[dict[str, Any]] = json.loads(
            self.registry_path.read_text(encoding="utf-8")
        )
        return [
            ExperimentRunRecord(
                run_id=item["run_id"],
                experiment_name=item["experiment_name"],
                run_name=item["run_name"],
                timestamp_utc=item["timestamp_utc"],
                params=item.get("params", {}),
                metrics=item.get("metrics", {}),
                tags=item.get("tags", {}),
                artifacts=item.get("artifacts", []),
            )
            for item in raw_list
        ]
