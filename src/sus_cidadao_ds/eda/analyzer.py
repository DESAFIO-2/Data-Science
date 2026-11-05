"""Analisador Exploratório de Dados (EDA) das camadas Silver e Gold (SPEC-01)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from sus_cidadao_ds.contracts.schemas import CanonicalMedication, DataManifest, NormativeChunk
from sus_cidadao_ds.core.mlflow_tracker import MLflowTracker


@dataclass(frozen=True)
class EDASummary:
    """Resumo quantitativo da Análise Exploratória de Dados (EDA)."""

    manifest_sha256: str
    total_medications: int
    unique_dcbs: int
    by_rename_component: dict[str, int]
    by_dispensation_route: dict[str, int]
    pfpb_free_count: int
    pfpb_free_rate: float
    requires_lme_count: int
    requires_lme_rate: float
    total_chunks: int
    chunks_by_source: dict[str, int]
    chunks_by_route_category: dict[str, int]
    avg_chunk_words: float
    median_chunk_words: float
    min_chunk_words: int
    max_chunk_words: int
    dcb_chunk_coverage_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EDAAnalyzer:
    """Executa perfilamento estatístico e gera relatório auditável das bases do SUS Cidadão."""

    def analyze(
        self,
        medications: list[CanonicalMedication],
        chunks: list[NormativeChunk],
        manifest: DataManifest,
        reports_dir: Path | None = None,
        tracker: MLflowTracker | None = None,
    ) -> EDASummary:
        """Calcula estatísticas descritivas das bases Silver/Gold e salva relatórios."""
        total_meds = len(medications)
        unique_dcbs_set = {m.dcb_name for m in medications}
        by_component = dict(Counter(m.rename_component for m in medications))
        by_route = dict(Counter(m.dispensation_route for m in medications))

        pfpb_free_count = sum(1 for m in medications if m.pfpb_free)
        lme_count = sum(1 for m in medications if m.requires_lme)

        total_chunks = len(chunks)
        chunks_by_source = dict(Counter(c.source_id for c in chunks))
        chunks_by_route = dict(Counter(c.route_category for c in chunks))

        word_counts = [len(c.text.split()) for c in chunks] if chunks else [0]
        avg_words = sum(word_counts) / len(word_counts)
        med_words = float(median(word_counts))

        mentioned_dcbs = {dcb for c in chunks for dcb in c.dcb_mentions}
        covered_dcbs = unique_dcbs_set.intersection(mentioned_dcbs)
        coverage_rate = (
            len(covered_dcbs) / len(unique_dcbs_set) if unique_dcbs_set else 0.0
        )

        summary = EDASummary(
            manifest_sha256=manifest.combined_sha256,
            total_medications=total_meds,
            unique_dcbs=len(unique_dcbs_set),
            by_rename_component=by_component,
            by_dispensation_route=by_route,
            pfpb_free_count=pfpb_free_count,
            pfpb_free_rate=round(pfpb_free_count / total_meds, 4) if total_meds else 0.0,
            requires_lme_count=lme_count,
            requires_lme_rate=round(lme_count / total_meds, 4) if total_meds else 0.0,
            total_chunks=total_chunks,
            chunks_by_source=chunks_by_source,
            chunks_by_route_category=chunks_by_route,
            avg_chunk_words=round(avg_words, 2),
            median_chunk_words=round(med_words, 2),
            min_chunk_words=min(word_counts),
            max_chunk_words=max(word_counts),
            dcb_chunk_coverage_rate=round(coverage_rate, 4),
        )

        markdown_report = self._render_markdown(summary)

        if reports_dir is not None:
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "eda_report.md").write_text(markdown_report, encoding="utf-8")
            (reports_dir / "eda_summary.json").write_text(
                json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        if tracker is not None:
            tracker.log_experiment_run(
                run_name="SPEC01_EDA_Silver_Gold_Profile",
                params={
                    "manifest_version": manifest.manifest_version,
                    "engineering_source": manifest.engineering_source,
                },
                metrics={
                    "total_medications": float(summary.total_medications),
                    "unique_dcbs": float(summary.unique_dcbs),
                    "pfpb_free_rate": summary.pfpb_free_rate,
                    "requires_lme_rate": summary.requires_lme_rate,
                    "total_chunks": float(summary.total_chunks),
                    "avg_chunk_words": summary.avg_chunk_words,
                    "dcb_chunk_coverage_rate": summary.dcb_chunk_coverage_rate,
                },
                tags={
                    "spec_id": "SPEC-01",
                    "manifest_sha256": manifest.combined_sha256,
                    "git_stage": "semana2_eda",
                },
                artifact_files={"eda_summary.json": summary.to_dict()},
            )

        return summary

    def _render_markdown(self, summary: EDASummary) -> str:
        lines = [
            "# Relatório de Análise Exploratória de Dados (EDA) — SUS Cidadão",
            "",
            f"- **Hash Consolidado do Manifesto (SHA-256):** `{summary.manifest_sha256}`",
            f"- **Total de Apresentações Canônicas (Gold):** `{summary.total_medications}`",
            f"- **Denominações Comuns Brasileiras (DCBs únicos):** `{summary.unique_dcbs}`",
            f"- **Total de Chunks Normativos (Silver):** `{summary.total_chunks}`",
            "",
            "## 1. Distribuição por Componente da RENAME 2024",
            "",
            "| Componente RENAME | Quantidade |",
            "|---|---|",
        ]
        for comp, count in sorted(summary.by_rename_component.items()):
            lines.append(f"| {comp} | {count} |")

        lines.extend(
            [
                "",
                "## 2. Distribuição por Via de Acesso Cidadão",
                "",
                "| Via de Dispensação | Quantidade | Regra Operacional |",
                "|---|---|---|",
            ]
        )
        route_notes = {
            "FARMACIA_POPULAR": "Drogaria privada credenciada (100% gratuito com CPF + Receita)",
            "UBS_ATENCAO_PRIMARIA": "Farmácia da UBS da Região Administrativa (CNS + CPF + Receita)",
            "ALTO_CUSTO_CEAF": "Farmácia de Alto Custo SES-DF (Processo LME + Exames PCDT + CID-10)",
        }
        for route, count in sorted(summary.by_dispensation_route.items()):
            lines.append(f"| `{route}` | {count} | {route_notes.get(route, '-')} |")

        lines.extend(
            [
                "",
                "## 3. Indicadores de Gratuidade e Complexidade",
                "",
                f"- **Gratuidade Plena Farmácia Popular (`pfpb_free`):** {summary.pfpb_free_count} itens ({summary.pfpb_free_rate * 100:.1f}%)",
                f"- **Exigência de Processo LME / Alto Custo (`requires_lme`):** {summary.requires_lme_count} itens ({summary.requires_lme_rate * 100:.1f}%)",
                f"- **Cobertura de DCBs nos Chunks Normativos:** {summary.dcb_chunk_coverage_rate * 100:.1f}%",
                "",
                "## 4. Perfilamento dos Chunks Normativos (Camada Silver)",
                "",
                f"- **Média de palavras por chunk:** `{summary.avg_chunk_words}`",
                f"- **Mediana de palavras por chunk:** `{summary.median_chunk_words}`",
                f"- **Intervalo (mín–máx palavras):** `{summary.min_chunk_words}` – `{summary.max_chunk_words}`",
                "",
                "| Fonte Normativa (`source_id`) | Chunks |",
                "|---|---|",
            ]
        )
        for src, count in sorted(summary.chunks_by_source.items()):
            lines.append(f"| `{src}` | {count} |")

        return "\n".join(lines) + "\n"

