"""Otimizador de limiar de abstenção (`min_score`) para TF-IDF Baseline e Hybrid Retriever (SPEC-03)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from sus_cidadao_ds.contracts.schemas import DataManifest, GoldenCase, RetrievalHit
from sus_cidadao_ds.core.mlflow_tracker import MLflowTracker


class SearchableRetriever(Protocol):
    """Protocolo para motores de busca compatíveis com calibração."""

    def search(
        self, query: str, top_k: int = 3, min_score: float = 0.12
    ) -> list[RetrievalHit]: ...


@dataclass(frozen=True)
class CalibrationPoint:
    """Métricas obtidas em um limiar específico `min_score`."""

    retriever_name: str
    min_score: float
    hit_rate_at_3: float
    recall_at_3: float
    mrr: float
    abstention_accuracy: float
    false_positive_rate: float
    combined_f1: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationSummary:
    """Resumo comparativo da calibração de limiares."""

    manifest_sha256: str
    baseline_tfidf_012: CalibrationPoint
    best_tfidf: CalibrationPoint
    best_hybrid: CalibrationPoint
    tfidf_curve: list[CalibrationPoint]
    hybrid_curve: list[CalibrationPoint]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ThresholdCalibrator:
    """Executa varredura de limiares `min_score` sobre o Golden Dataset e registra no MLflow."""

    DEFAULT_GRID: tuple[float, ...] = (
        0.05,
        0.08,
        0.10,
        0.12,
        0.15,
        0.18,
        0.20,
        0.22,
        0.25,
        0.30,
        0.35,
    )

    def evaluate_at_threshold(
        self,
        retriever: SearchableRetriever,
        retriever_name: str,
        golden_cases: list[GoldenCase],
        min_score: float,
        top_k: int = 3,
    ) -> CalibrationPoint:
        """Avalia um recuperador em um único limiar `min_score`."""
        # Filtra casos que testam recuperação vs abstenção fora de elenco (exclui bloqueios clínicos puros)
        ir_cases = [c for c in golden_cases if not c.is_clinical_block]
        positive_cases = [c for c in ir_cases if not c.should_abstain]
        negative_cases = [c for c in ir_cases if c.should_abstain]

        hits_count = 0
        recall_sum = 0.0
        rr_sum = 0.0

        for case in positive_cases:
            results = retriever.search(case.query, top_k=top_k, min_score=min_score)
            retrieved_ids = [r.chunk_id for r in results]
            relevant_set = set(case.relevant_chunk_ids)

            if any(cid in relevant_set for cid in retrieved_ids):
                hits_count += 1

            if relevant_set:
                matched = sum(1 for cid in retrieved_ids if cid in relevant_set)
                recall_sum += matched / len(relevant_set)

            for rank, cid in enumerate(retrieved_ids, start=1):
                if cid in relevant_set:
                    rr_sum += 1.0 / rank
                    break

        n_pos = len(positive_cases) or 1
        hit_rate = hits_count / n_pos
        recall_at_k = recall_sum / n_pos
        mrr = rr_sum / n_pos

        correct_abstentions = 0
        false_positives = 0
        for case in negative_cases:
            results = retriever.search(case.query, top_k=top_k, min_score=min_score)
            if len(results) == 0:
                correct_abstentions += 1
            else:
                false_positives += 1

        n_neg = len(negative_cases) or 1
        abstention_acc = correct_abstentions / n_neg
        fpr = false_positives / n_neg

        if (recall_at_k + abstention_acc) > 0:
            combined_f1 = (2.0 * recall_at_k * abstention_acc) / (
                recall_at_k + abstention_acc
            )
        else:
            combined_f1 = 0.0

        return CalibrationPoint(
            retriever_name=retriever_name,
            min_score=round(min_score, 4),
            hit_rate_at_3=round(hit_rate, 4),
            recall_at_3=round(recall_at_k, 4),
            mrr=round(mrr, 4),
            abstention_accuracy=round(abstention_acc, 4),
            false_positive_rate=round(fpr, 4),
            combined_f1=round(combined_f1, 4),
        )

    def run_calibration(
        self,
        tfidf_retriever: SearchableRetriever,
        hybrid_retriever: SearchableRetriever,
        golden_cases: list[GoldenCase],
        manifest: DataManifest,
        reports_dir: Path | None = None,
        tracker: MLflowTracker | None = None,
    ) -> CalibrationSummary:
        """Executa a varredura de limiares para TF-IDF e Hybrid Retriever."""
        tfidf_curve = [
            self.evaluate_at_threshold(
                tfidf_retriever, "tfidf_baseline", golden_cases, th
            )
            for th in self.DEFAULT_GRID
        ]
        hybrid_curve = [
            self.evaluate_at_threshold(
                hybrid_retriever, "hybrid_dcb_rrf", golden_cases, th
            )
            for th in self.DEFAULT_GRID
        ]

        baseline_012 = next(
            (pt for pt in tfidf_curve if abs(pt.min_score - 0.12) < 1e-6),
            tfidf_curve[0],
        )
        best_tfidf = max(
            tfidf_curve, key=lambda pt: (pt.combined_f1, pt.mrr, pt.hit_rate_at_3)
        )
        best_hybrid = max(
            hybrid_curve, key=lambda pt: (pt.combined_f1, pt.mrr, pt.hit_rate_at_3)
        )

        summary = CalibrationSummary(
            manifest_sha256=manifest.combined_sha256,
            baseline_tfidf_012=baseline_012,
            best_tfidf=best_tfidf,
            best_hybrid=best_hybrid,
            tfidf_curve=tfidf_curve,
            hybrid_curve=hybrid_curve,
        )

        if reports_dir is not None:
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "calibration_curve.json").write_text(
                json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (reports_dir / "calibration_report.md").write_text(
                self._render_markdown(summary),
                encoding="utf-8",
            )

        if tracker is not None:
            tracker.log_experiment_run(
                run_name="SPEC03_TFIDF_Baseline_012",
                params={
                    "retriever_type": "tfidf_baseline",
                    "min_score": baseline_012.min_score,
                    "top_k": 3,
                },
                metrics={
                    "hit_rate_at_3": baseline_012.hit_rate_at_3,
                    "recall_at_3": baseline_012.recall_at_3,
                    "mrr": baseline_012.mrr,
                    "abstention_accuracy": baseline_012.abstention_accuracy,
                    "combined_f1": baseline_012.combined_f1,
                },
                tags={
                    "spec_id": "SPEC-03",
                    "manifest_sha256": manifest.combined_sha256,
                    "git_stage": "semana2_baseline",
                },
            )
            tracker.log_experiment_run(
                run_name="SPEC03_Hybrid_Calibrated_Best",
                params={
                    "retriever_type": "hybrid_dcb_rrf",
                    "min_score": best_hybrid.min_score,
                    "top_k": 3,
                    "rrf_k": 60,
                },
                metrics={
                    "hit_rate_at_3": best_hybrid.hit_rate_at_3,
                    "recall_at_3": best_hybrid.recall_at_3,
                    "mrr": best_hybrid.mrr,
                    "abstention_accuracy": best_hybrid.abstention_accuracy,
                    "combined_f1": best_hybrid.combined_f1,
                },
                tags={
                    "spec_id": "SPEC-03",
                    "manifest_sha256": manifest.combined_sha256,
                    "git_stage": "semana2_hybrid_calibrated",
                },
                artifact_files={"calibration_curve.json": summary.to_dict()},
            )

        return summary

    def _render_markdown(self, summary: CalibrationSummary) -> str:
        lines = [
            "# Relatório de Calibração de Limiar de Abstenção (`min_score`) — SPEC-03",
            "",
            f"- **Hash Consolidado do Manifesto (SHA-256):** `{summary.manifest_sha256}`",
            "",
            "## 1. Resumo Executivo (Baseline ADR-003 vs. Limiares Calibrados)",
            "",
            "| Configuração | `min_score` | Hit Rate@3 | Recall@3 | MRR | Abstention Acc | Combined F1 |",
            "|---|---|---|---|---|---|---|",
            (
                f"| **TF-IDF Baseline (ADR-003)** | `{summary.baseline_tfidf_012.min_score}` "
                f"| {summary.baseline_tfidf_012.hit_rate_at_3:.4f} | {summary.baseline_tfidf_012.recall_at_3:.4f} "
                f"| {summary.baseline_tfidf_012.mrr:.4f} | {summary.baseline_tfidf_012.abstention_accuracy:.4f} "
                f"| {summary.baseline_tfidf_012.combined_f1:.4f} |"
            ),
            (
                f"| **TF-IDF Calibrado (Ótimo)** | `{summary.best_tfidf.min_score}` "
                f"| {summary.best_tfidf.hit_rate_at_3:.4f} | {summary.best_tfidf.recall_at_3:.4f} "
                f"| {summary.best_tfidf.mrr:.4f} | {summary.best_tfidf.abstention_accuracy:.4f} "
                f"| **{summary.best_tfidf.combined_f1:.4f}** |"
            ),
            (
                f"| **Hybrid Retriever (DCB + RRF Ótimo)** | `{summary.best_hybrid.min_score}` "
                f"| **{summary.best_hybrid.hit_rate_at_3:.4f}** | **{summary.best_hybrid.recall_at_3:.4f}** "
                f"| **{summary.best_hybrid.mrr:.4f}** | **{summary.best_hybrid.abstention_accuracy:.4f}** "
                f"| **{summary.best_hybrid.combined_f1:.4f}** |"
            ),
            "",
            "## 2. Curva de Calibração — Hybrid Retriever (`hybrid_dcb_rrf`)",
            "",
            "| `min_score` | Hit Rate@3 | Recall@3 | MRR | Abstention Acc | FPR | Combined F1 |",
            "|---|---|---|---|---|---|---|",
        ]
        for pt in summary.hybrid_curve:
            lines.append(
                f"| `{pt.min_score:.2f}` | {pt.hit_rate_at_3:.4f} | {pt.recall_at_3:.4f} "
                f"| {pt.mrr:.4f} | {pt.abstention_accuracy:.4f} | {pt.false_positive_rate:.4f} "
                f"| {pt.combined_f1:.4f} |"
            )
        return "\n".join(lines) + "\n"

