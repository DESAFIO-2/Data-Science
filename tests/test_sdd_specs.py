"""Testes unitários e de integração validando SPEC-00 a SPEC-05 (SDD)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from sus_cidadao_ds.agents.orchestrator import MultiAgentOrchestrator
from sus_cidadao_ds.calibration.threshold_optimizer import ThresholdCalibrator
from sus_cidadao_ds.contracts.schemas import GoldenCase, compute_sha256
from sus_cidadao_ds.core.config import ProjectPaths
from sus_cidadao_ds.core.mlflow_tracker import MLflowTracker
from sus_cidadao_ds.eda.analyzer import EDAAnalyzer
from sus_cidadao_ds.evaluation.ragas_benchmark import RAGASBenchmarkRunner
from sus_cidadao_ds.guardrails.clinical_blocker import ClinicalBlocker
from sus_cidadao_ds.guardrails.pii_masker import PIIMasker
from sus_cidadao_ds.ingestion.infosaude_client import InfoSaudeLiveClient, haversine_km
from sus_cidadao_ds.ingestion.pdf_pipeline import UnifiedPDFPipeline
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager
from sus_cidadao_ds.retrieval.retrievers import (
    BM25Retriever,
    HybridRetriever,
    TabularDCBMatcher,
    TFIDFRetriever,
)
from sus_cidadao_ds.sync.data_sync import DataSynchronizer


class TestSDDSpecifications(unittest.TestCase):
    """Verifica os critérios de aceite de todas as especificações SDD (SPEC-00 a SPEC-05)."""

    def setUp(self) -> None:
        self.paths = ProjectPaths.from_root()
        self.syncer = DataSynchronizer(self.paths)
        self.manifest = self.syncer.sync()
        self.medications = self.syncer.load_medications()
        self.chunks = self.syncer.load_chunks()
        golden_raw = json.loads(
            (self.paths.datasets_dir / "golden_set_v1.json").read_text(encoding="utf-8")
        )
        self.golden_cases = [GoldenCase.from_dict(item) for item in golden_raw]

    def test_spec00_mlflow_tracker_and_lineage(self) -> None:
        """SPEC-00: MLflowTracker deve registrar parâmetros, métricas, tags e artefatos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tracker = MLflowTracker(
                mlruns_dir=tmp_path / "mlruns",
                registry_path=tmp_path / "registry.json",
            )
            record = tracker.log_experiment_run(
                run_name="test_run_sdd",
                params={"top_k": 3, "min_score": 0.12},
                metrics={"mrr": 0.95, "hit_rate_at_3": 1.0},
                tags={"spec_id": "SPEC-00", "manifest_sha256": self.manifest.combined_sha256},
                artifact_files={"sample.json": {"ok": True}},
            )
            self.assertEqual(record.run_name, "test_run_sdd")
            self.assertEqual(record.metrics["mrr"], 0.95)
            runs = tracker.list_runs()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].tags["spec_id"], "SPEC-00")

    def test_spec01_sync_and_eda_integrity(self) -> None:
        """SPEC-01: Sincronização Silver/Gold deve validar SHA-256 e EDA deve cobrir 100% dos DCBs."""
        self.assertGreaterEqual(len(self.medications), 20)
        self.assertGreaterEqual(len(self.chunks), 8)

        for chunk in self.chunks:
            self.assertEqual(chunk.sha256, compute_sha256(chunk.text))

        analyzer = EDAAnalyzer()
        summary = analyzer.analyze(
            medications=self.medications,
            chunks=self.chunks,
            manifest=self.manifest,
        )
        self.assertEqual(summary.total_medications, len(self.medications))
        self.assertGreater(summary.pfpb_free_rate, 0.40)
        self.assertGreater(summary.requires_lme_rate, 0.20)
        self.assertGreaterEqual(summary.dcb_chunk_coverage_rate, 0.95)

    def test_spec02_golden_dataset_referential_integrity(self) -> None:
        """SPEC-02: Todos os chunk_ids e DCBs esperados no Golden Dataset devem existir em Silver/Gold."""
        valid_chunk_ids = {c.chunk_id for c in self.chunks}
        valid_dcbs = {m.dcb_name for m in self.medications}

        self.assertEqual(len(self.golden_cases), 16)
        for case in self.golden_cases:
            for cid in case.relevant_chunk_ids:
                self.assertIn(
                    cid,
                    valid_chunk_ids,
                    f"Chunk {cid} do caso {case.case_id} não existe na camada Silver",
                )
            for dcb in case.expected_dcb:
                self.assertIn(
                    dcb,
                    valid_dcbs,
                    f"DCB {dcb} do caso {case.case_id} não existe na camada Gold",
                )
            if case.should_abstain:
                self.assertEqual(case.relevant_chunk_ids, [])

    def test_spec03_retrievers_and_threshold_calibration(self) -> None:
        """SPEC-03: TF-IDF baseline (0.12) e Hybrid Retriever devem recuperar chunks corretos e calibrar."""
        tfidf = TFIDFRetriever(self.chunks)
        bm25 = BM25Retriever(self.chunks)
        hybrid = HybridRetriever(self.medications, self.chunks)
        tabular = TabularDCBMatcher(self.medications)

        # Consulta clássica da Engenharia de Dados: "losartana potássica 50 mg"
        hits_tfidf = tfidf.search("losartana potássica 50 mg", top_k=3, min_score=0.12)
        self.assertGreaterEqual(len(hits_tfidf), 1)
        self.assertEqual(hits_tfidf[0].chunk_id, "CHK-PFPB-001")

        hits_bm25 = bm25.search("metformina 500 mg", top_k=3, min_score=0.15)
        self.assertGreaterEqual(len(hits_bm25), 1)
        self.assertEqual(hits_bm25[0].chunk_id, "CHK-PFPB-001")

        dcb_matches = tabular.match_medications("adalimumabe 40 mg injetável")
        self.assertEqual(dcb_matches[0][1].dcb_name, "adalimumabe")

        calibrator = ThresholdCalibrator()
        cal_summary = calibrator.run_calibration(
            tfidf_retriever=tfidf,
            hybrid_retriever=hybrid,
            golden_cases=self.golden_cases,
            manifest=self.manifest,
        )
        self.assertGreaterEqual(
            cal_summary.best_hybrid.combined_f1,
            cal_summary.baseline_tfidf_012.combined_f1,
        )
        self.assertEqual(cal_summary.best_hybrid.hit_rate_at_3, 1.0)
        self.assertEqual(cal_summary.best_hybrid.abstention_accuracy, 1.0)

    def test_spec04_ragas_scientific_benchmark(self) -> None:
        """SPEC-04: RAG Híbrido Multiagentes deve superar LLM Pura e RAG TF-IDF nas métricas RAGAS."""
        runner = RAGASBenchmarkRunner(
            medications=self.medications,
            chunks=self.chunks,
            golden_cases=self.golden_cases,
        )
        metrics_list = runner.run_all(manifest=self.manifest)
        by_name = {m.system_name: m for m in metrics_list}

        llm_pure = by_name["01_LLM_Pura_Sem_RAG"]
        rag_tfidf = by_name["02_RAG_TFIDF_Baseline_012"]
        rag_hybrid = by_name["03_RAG_Hibrido_Multiagentes"]

        self.assertGreater(rag_hybrid.faithfulness, llm_pure.faithfulness)
        self.assertGreater(rag_hybrid.ragas_harmonic_score, rag_tfidf.ragas_harmonic_score)
        self.assertEqual(rag_hybrid.clinical_guardrail_pass_rate, 1.0)
        self.assertEqual(rag_hybrid.route_accuracy, 1.0)

    def test_spec05_guardrails_and_multiagent_orchestrator(self) -> None:
        """SPEC-05: Guardrails LGPD/CFM e Orquestrador Multiagentes devem funcionar ponta a ponta."""
        masker = PIIMasker()
        masked = masker.mask(
            "Paciente: Maria Aparecida Souza, CPF 123.456.789-01, CNS 700 1234 5678 9012, "
            "tel (61) 99876-5432. Receita de losartana potássica 50 mg em Ceilândia."
        )
        self.assertNotIn("123.456.789-01", masked.sanitized_text)
        self.assertNotIn("Maria Aparecida Souza", masked.sanitized_text)
        self.assertEqual(masked.redaction_count, 4)
        self.assertIn("losartana potássica 50 mg", masked.sanitized_text)

        blocker = ClinicalBlocker()
        blocked = blocker.inspect(
            "Minha pressão subiu para 18x11 com dor no peito, posso dobrar a dose da losartana?"
        )
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(blocked.has_red_flag_emergency)

        orchestrator = MultiAgentOrchestrator(
            medications=self.medications, chunks=self.chunks
        )
        # Caso complexo multicanal + SISREG + alerta de vencimento RF08
        response = orchestrator.run(
            "Paciente: João Silva, CPF 111.222.333-44. Receita de losartana potássica 50 mg, "
            "adalimumabe 40 mg e pedido de Ecocardiograma Transtorácico. Moro em Ceilândia.",
            days_since_emission=170,
        )
        self.assertFalse(response.is_clinical_block)
        self.assertEqual(response.detected_ra, "Ceilândia - DF")
        self.assertEqual(len(response.audited_medications), 2)
        self.assertEqual(len(response.sisreg_guidance), 1)
        self.assertEqual(len(response.agent_trace), 4)
        self.assertTrue(
            any("ALERTA" in alert for alert in response.validity_alerts)
        )

    def test_spec06_infosaude_live_stock_and_maps(self) -> None:
        """SPEC-06: InfoSaudeLiveClient deve decodificar DSR de estoque CEAF e mapas do DF."""
        client = InfoSaudeLiveClient(gold_dir=self.paths.gold_dir)
        if not (self.paths.gold_dir / "ceaf_live_stock.json").exists():
            client.sync_from_snapshots_or_live(prefer_live=False)

        matches = client.query_medication_stock("adalimumabe")
        self.assertGreaterEqual(len(matches), 3)
        units = {m.unidade for m in matches}
        self.assertEqual(units, {"Asa Sul", "Ceilândia", "Gama"})

        pharmacies = client.find_pharmacies_by_ra("Ceilândia", top_k=5)
        self.assertGreaterEqual(len(pharmacies), 1)
        self.assertTrue(any("Ceilândia" in p.name or "CEILANDIA" in p.name for p in pharmacies))

        dist = haversine_km(-15.8055, -47.8900, -15.8132, -48.1035)
        self.assertGreater(dist, 15.0)
        self.assertLess(dist, 30.0)

    def test_spec07_chromadb_vectorstore(self) -> None:
        """SPEC-07: ChromaVectorStoreManager deve indexar e consultar coleções com filtros."""
        manager = ChromaVectorStoreManager(vectorstore_dir=self.paths.data_dir / "vectorstore")
        summary = manager.index_all(self.paths)
        self.assertGreaterEqual(summary.stock_count, 800)
        self.assertGreaterEqual(summary.pharmacies_count, 200)
        self.assertGreaterEqual(summary.protocols_count, 30)

        # Consulta com filtro de metadados na coleção ceaf_live_stock
        hits_stock = manager.search(
            query="adalimumabe 40 mg injetavel",
            collection_name=manager.COLLECTION_STOCK,
            where_filter={"tem_estoque": True},
            top_k=3,
        )
        self.assertGreaterEqual(len(hits_stock), 1)
        self.assertTrue(hits_stock[0].metadata["tem_estoque"])
        self.assertIn("ADALIMUMABE", hits_stock[0].document.upper())

        # Consulta semântica na coleção df_pharmacies
        hits_pharm = manager.search(
            query="Farmácia de Alto Custo Ceilândia",
            collection_name=manager.COLLECTION_PHARMACIES,
            top_k=2,
        )
        self.assertGreaterEqual(len(hits_pharm), 1)
        self.assertIn("CEILANDIA", hits_pharm[0].document.upper())

    def test_spec08_unified_pdf_pipeline_and_chroma_rag(self) -> None:
        """SPEC-08: Pipeline unificado de PDFs, conversão JSON->PDF, indexação e avaliação RAGAS."""
        pipeline = UnifiedPDFPipeline(self.paths)
        summary = pipeline.run()

        self.assertGreaterEqual(summary.official_pdfs_count, 4)
        self.assertGreaterEqual(summary.converted_pdfs_count, 3)
        self.assertGreaterEqual(summary.total_pdfs_processed, 7)
        self.assertGreaterEqual(summary.total_chunks_extracted, 50)
        self.assertTrue(Path(summary.silver_chunks_path).exists())

        # Verifica existência física dos arquivos PDF
        pdf_dir = self.paths.raw_dir / "pdfs"
        for expected_name in (
            "F01_RENAME_2024.pdf",
            "F03_REME_DF_2026.pdf",
            "F04_ELENCO_FARMACIA_POPULAR_PFPB.pdf",
            "F12_CARTA_SERVICOS_HUB_UNB.pdf",
            "RELATORIO_ESTOQUE_CEAF_INFOSAUDE.pdf",
            "GUIA_FARMACIAS_UBS_GEO_DF.pdf",
            "CATALOGO_CANONICO_MEDICAMENTOS_SUS.pdf",
        ):
            self.assertTrue(
                (pdf_dir / expected_name).exists(),
                f"PDF obrigatório {expected_name} não encontrado em {pdf_dir}",
            )

        # Indexação no ChromaDB
        manager = ChromaVectorStoreManager(vectorstore_dir=self.paths.data_dir / "vectorstore")
        n_indexed = manager.index_unified_pdf_chunks(Path(summary.silver_chunks_path))
        self.assertGreaterEqual(n_indexed, 50)

        # Busca semântica no corpus unificado
        hits = manager.search_unified_corpus("Omalizumabe 150mg asma grave", top_k=3)
        self.assertGreaterEqual(len(hits), 1)
        self.assertGreater(hits[0].relevance_score, 0.30)

        # Reavaliação RAGAS completa incluindo o sistema 04_RAG_ChromaDB_Corpus_PDFs
        runner = RAGASBenchmarkRunner(
            medications=self.medications,
            chunks=self.chunks,
            golden_cases=self.golden_cases,
            vectorstore_manager=manager,
        )
        results = runner.run_all(
            manifest=self.manifest,
            reports_dir=self.paths.reports_dir,
            baselines_dir=self.paths.baselines_dir,
        )
        self.assertEqual(len(results), 4)

        chroma_eval = results[3]
        self.assertEqual(chroma_eval.system_name, "04_RAG_ChromaDB_Corpus_PDFs")
        self.assertGreaterEqual(chroma_eval.hit_rate_at_3, 0.95)
        self.assertGreaterEqual(chroma_eval.route_accuracy, 0.95)
        self.assertGreaterEqual(chroma_eval.faithfulness, 0.95)
        self.assertEqual(chroma_eval.clinical_guardrail_pass_rate, 1.0)


if __name__ == "__main__":
    unittest.main()

