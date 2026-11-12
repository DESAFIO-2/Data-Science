"""Configurações globais e resolução de diretórios do SUS Cidadão Data-Science."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Estrutura de caminhos determinísticos do repositório Data-Science."""

    root: Path
    config_dir: Path
    specs_dir: Path
    data_dir: Path
    manifests_dir: Path
    raw_dir: Path
    silver_dir: Path
    gold_dir: Path
    artifacts_dir: Path
    evals_dir: Path
    datasets_dir: Path
    baselines_dir: Path
    reports_dir: Path
    dags_dir: Path

    @classmethod
    def from_root(cls, root: Path | None = None) -> ProjectPaths:
        """Resolve todos os caminhos a partir da raiz do repositório."""
        resolved_root = (
            root.resolve()
            if root is not None
            else Path(__file__).resolve().parents[3]
        )
        data_dir = resolved_root / "data"
        evals_dir = resolved_root / "evals"
        return cls(
            root=resolved_root,
            config_dir=resolved_root / "config",
            specs_dir=resolved_root / "specs",
            data_dir=data_dir,
            manifests_dir=data_dir / "manifests",
            raw_dir=data_dir / "raw",
            silver_dir=data_dir / "silver",
            gold_dir=data_dir / "gold",
            artifacts_dir=resolved_root / ".artifacts",
            evals_dir=evals_dir,
            datasets_dir=evals_dir / "datasets",
            baselines_dir=evals_dir / "baselines",
            reports_dir=evals_dir / "reports",
            dags_dir=resolved_root / "dags",
        )

    def ensure_dirs(self) -> None:
        """Garante a existência de todos os diretórios operacionais."""
        for directory in (
            self.config_dir,
            self.specs_dir,
            self.manifests_dir,
            self.raw_dir,
            self.silver_dir,
            self.gold_dir,
            self.artifacts_dir,
            self.datasets_dir,
            self.baselines_dir,
            self.reports_dir,
            self.dags_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

