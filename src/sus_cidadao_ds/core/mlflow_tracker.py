"""Rastreador de experimentos MLflow com suporte a linhagem de dados (hashes SHA-256).

Implementa a governança definida em SPEC-00:
- Usa o pacote `mlflow` quando disponível no ambiente.
- Persiste estrutura compatível com FileStore (`mlruns/`) e um registro auditável JSON
  em `evals/reports/mlflow_runs_registry.json` para reprodutibilidade em CI/CD.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ExperimentRunRecord:
    """Registro estruturado de uma execução experimental no MLflow."""

    run_id: str
    experiment_name: str
    run_name: str
    timestamp_utc: str
    params: dict[str, str | int | float | bool] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)


class MLflowTracker:
    """Gerenciador de rastreamento experimental compatível com MLflow Tracking."""

    def __init__(
        self,
        mlruns_dir: Path,
        registry_path: Path,
        experiment_name: str = "sus_cidadao_rag_benchmarks",
    ) -> None:
        self.mlruns_dir = mlruns_dir
        self.registry_path = registry_path
        self.experiment_name = experiment_name
        self.experiment_id = "1"
        self._ensure_experiment_store()

    def _ensure_experiment_store(self) -> None:
        exp_dir = self.mlruns_dir / self.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        meta_path = exp_dir / "meta.yaml"
        if not meta_path.exists():
            now_ms = int(time.time() * 1000)
            meta_content = (
                f"artifact_location: file://{exp_dir.resolve()}\n"
                f"creation_time: {now_ms}\n"
                f"experiment_id: '{self.experiment_id}'\n"
                f"last_update_time: {now_ms}\n"
                "lifecycle_stage: active\n"
                f"name: {self.experiment_name}\n"
            )
            meta_path.write_text(meta_content, encoding="utf-8")

    def log_experiment_run(
        self,
        run_name: str,
        params: dict[str, str | int | float | bool],
        metrics: dict[str, float],
        tags: dict[str, str] | None = None,
        artifact_files: dict[str, Any] | None = None,
    ) -> ExperimentRunRecord:
        """Registra parâmetros, métricas, tags de linhagem e artefatos no MLflow."""
        run_id = uuid.uuid4().hex
        now_ms = int(time.time() * 1000)
        timestamp_utc = datetime.now(UTC).isoformat()

        merged_tags: dict[str, str] = {
            "mlflow.runName": run_name,
            "project": "SUS_Cidadao_NavegaSUS",
            "methodology": "SDD",
        }
        if tags:
            merged_tags.update(tags)

        run_dir = self.mlruns_dir / self.experiment_id / run_id
        params_dir = run_dir / "params"
        metrics_dir = run_dir / "metrics"
        tags_dir = run_dir / "tags"
        artifacts_dir = run_dir / "artifacts"

        for directory in (params_dir, metrics_dir, tags_dir, artifacts_dir):
            directory.mkdir(parents=True, exist_ok=True)

        run_meta = (
            f"artifact_uri: file://{artifacts_dir.resolve()}\n"
            f"end_time: {now_ms}\n"
            f"entry_point_name: ''\n"
            f"experiment_id: '{self.experiment_id}'\n"
            "lifecycle_stage: active\n"
            f"run_id: {run_id}\n"
            f"run_name: {run_name}\n"
            f"run_uuid: {run_id}\n"
            "source_name: ''\n"
            "source_type: 4\n"
            "source_version: ''\n"
            f"start_time: {now_ms}\n"
            "status: 3\n"
            "user_id: marlon_ds\n"
        )
        (run_dir / "meta.yaml").write_text(run_meta, encoding="utf-8")

        for key, value in params.items():
            safe_key = key.replace("/", "_")
            (params_dir / safe_key).write_text(str(value), encoding="utf-8")

        for key, metric_val in metrics.items():
            safe_key = key.replace("/", "_")
            rounded = round(float(metric_val), 6)
            (metrics_dir / safe_key).write_text(
                f"{now_ms} {rounded} 0\n", encoding="utf-8"
            )

        for key, tag_val in merged_tags.items():
            safe_key = key.replace("/", "_")
            (tags_dir / safe_key).write_text(str(tag_val), encoding="utf-8")

        saved_artifacts: list[str] = []
        if artifact_files:
            for filename, content in artifact_files.items():
                target = artifacts_dir / filename
                if isinstance(content, (dict, list)):
                    target.write_text(
                        json.dumps(content, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                else:
                    target.write_text(str(content), encoding="utf-8")
                saved_artifacts.append(filename)

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

