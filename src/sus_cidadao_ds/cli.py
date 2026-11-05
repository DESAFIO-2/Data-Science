"""Interface de Linha de Comando (CLI) unificada do SUS Cidadão Data-Science."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sus_cidadao_ds.agents.orchestrator import MultiAgentOrchestrator
from sus_cidadao_ds.calibration.threshold_optimizer import ThresholdCalibrator
from sus_cidadao_ds.contracts.schemas import GoldenCase
from sus_cidadao_ds.core.config import ProjectPaths
from sus_cidadao_ds.core.mlflow_tracker import MLflowTracker
from sus_cidadao_ds.eda.analyzer import EDAAnalyzer
from sus_cidadao_ds.evaluation.ragas_benchmark import RAGASBenchmarkRunner
from sus_cidadao_ds.ingestion.infosaude_client import InfoSaudeLiveClient
from sus_cidadao_ds.ingestion.pdf_pipeline import UnifiedPDFPipeline
from sus_cidadao_ds.retrieval.chroma_indexer import ChromaVectorStoreManager
from sus_cidadao_ds.retrieval.retrievers import (
    BM25Retriever,
    HybridRetriever,
    TFIDFRetriever,
)
from sus_cidadao_ds.sync.data_sync import DataSynchronizer


def _load_golden_cases(paths: ProjectPaths) -> list[GoldenCase]:
    golden_path = paths.datasets_dir / "golden_set_v1.json"
    raw = json.loads(golden_path.read_text(encoding="utf-8"))
    return [GoldenCase.from_dict(item) for item in raw]


def main(argv: list[str] | None = None) -> int:
    """Entrypoint principal da CLI `sus-cidadao-ds`."""
    parser = argparse.ArgumentParser(
        prog="sus-cidadao-ds",
        description="Pipeline SDD de Ciência de Dados do SUS Cidadão (NavegaSUS)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. sync
    p_sync = subparsers.add_parser(
        "sync", help="Sincroniza camadas Silver/Gold e gera manifesto SHA-256"
    )
    p_sync.add_argument(
        "--engineering-dir",
        type=Path,
        default=None,
        help="Caminho opcional para o repositório local engenharia-dados",
    )

    # 2. eda
    subparsers.add_parser(
        "eda", help="Executa Análise Exploratória de Dados (EDA) e loga no MLflow"
    )

    # 3. search
    p_search = subparsers.add_parser(
        "search",
        help="Consulta motores de recuperação (compatível com sus_cidadao_data.rag.cli)",
    )
    p_search.add_argument("query", type=str, help="Consulta do cidadão ou medicamento")
    p_search.add_argument(
        "--retriever",
        choices=["tfidf", "bm25", "hybrid"],
        default="hybrid",
        help="Motor de recuperação (padrão: hybrid)",
    )
    p_search.add_argument("--top-k", type=int, default=3, help="Top-K resultados")
    p_search.add_argument(
        "--min-score", type=float, default=0.12, help="Limiar mínimo de abstenção"
    )

    # 4. calibrate
    subparsers.add_parser(
        "calibrate",
        help="Calibra cientificamente o limiar min_score no Golden Dataset + MLflow",
    )

    # 5. eval
    subparsers.add_parser(
        "eval",
        help="Executa benchmark científico RAGAS (LLM Pura vs RAG TF-IDF vs RAG Híbrido) + MLflow",
    )

    # 6. audit
    p_audit = subparsers.add_parser(
        "audit",
        help="Executa o Orquestrador Multiagentes (4 Agentes + Guardrails LGPD/CFM)",
    )
    p_audit.add_argument(
        "input_text", type=str, help="Texto da receita, dúvida ou transcrição de voz"
    )
    p_audit.add_argument(
        "--days-emitted",
        type=int,
        default=166,
        help="Dias decorridos desde a emissão da receita para alerta RF08 (15d/7d)",
    )

    # 7. sync-infosaude (SPEC-06)
    p_infosaude = subparsers.add_parser(
        "sync-infosaude",
        help="Sincroniza estoque em tempo real CEAF-DF e mapas das farmácias da API Power BI InfoSaúde",
    )
    p_infosaude.add_argument(
        "--live",
        action="store_true",
        help="Força consulta HTTP ao vivo em wabi-brazil-south-api.analysis.windows.net",
    )

    # 8. check-stock (SPEC-06)
    p_stock = subparsers.add_parser(
        "check-stock",
        help="Consulta disponibilidade de estoque CEAF e mapas de farmácias por RA",
    )
    p_stock.add_argument("medication", type=str, help="Nome do medicamento (ex.: adalimumabe)")
    p_stock.add_argument("--ra", type=str, default="Ceilândia", help="Região Administrativa do DF")

    # 9. index-chroma (SPEC-07)
    subparsers.add_parser(
        "index-chroma",
        help="Indexa dados estruturados JSON (estoque, farmácias, protocolos) no ChromaDB",
    )

    # 10. search-chroma (SPEC-07)
    p_chroma = subparsers.add_parser(
        "search-chroma",
        help="Consulta semântica com filtro por metadados no ChromaDB",
    )
    p_chroma.add_argument("query", type=str, help="Pergunta ou termo de busca")
    p_chroma.add_argument(
        "--collection",
        choices=[
            "ceaf_live_stock",
            "df_pharmacies",
            "sus_normative_protocols",
            "sus_unified_pdf_corpus",
        ],
        default="ceaf_live_stock",
        help="Coleção do ChromaDB para consulta",
    )
    p_chroma.add_argument("--top-k", type=int, default=3, help="Top-K documentos")
    p_chroma.add_argument(
        "--unidade",
        type=str,
        default=None,
        help="Filtro de unidade CEAF (ex: Ceilândia, Asa Sul, Gama)",
    )
    p_chroma.add_argument(
        "--somente-com-estoque",
        action="store_true",
        help="Filtra apenas registros com estoque disponível",
    )

    # 11. pipeline-pdf (SPEC-08)
    subparsers.add_parser(
        "pipeline-pdf",
        help="Executa o pipeline unificado: coleta PDFs, converte JSON->PDF, extrai chunks e indexa no ChromaDB",
    )

    args = parser.parse_args(argv)
    paths = ProjectPaths.from_root()
    paths.ensure_dirs()
    syncer = DataSynchronizer(paths)
    tracker = MLflowTracker(
        mlruns_dir=paths.mlruns_dir,
        registry_path=paths.reports_dir / "mlflow_runs_registry.json",
    )

    if args.command == "sync":
        manifest = syncer.sync(engineering_dir=args.engineering_dir)
        print(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
        return 0

    manifest = syncer.load_manifest()
    meds = syncer.load_medications()
    chunks = syncer.load_chunks()

    if args.command == "eda":
        analyzer = EDAAnalyzer()
        summary = analyzer.analyze(
            medications=meds,
            chunks=chunks,
            manifest=manifest,
            reports_dir=paths.reports_dir,
            tracker=tracker,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "search":
        if args.retriever == "tfidf":
            hits = TFIDFRetriever(chunks).search(
                args.query, top_k=args.top_k, min_score=args.min_score
            )
        elif args.retriever == "bm25":
            hits = BM25Retriever(chunks).search(
                args.query, top_k=args.top_k, min_score=args.min_score
            )
        else:
            hits = HybridRetriever(meds, chunks).search(
                args.query, top_k=args.top_k, min_score=args.min_score
            )
        payload = [
            {
                "chunk_id": h.chunk_id,
                "score": h.score,
                "source_id": h.source_id,
                "route_category": h.route_category,
                "matched_dcb": h.matched_dcb,
                "section": h.section,
                "page_number": h.page_number,
            }
            for h in hits
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "calibrate":
        golden_cases = _load_golden_cases(paths)
        calibrator = ThresholdCalibrator()
        cal_summary = calibrator.run_calibration(
            tfidf_retriever=TFIDFRetriever(chunks),
            hybrid_retriever=HybridRetriever(meds, chunks),
            golden_cases=golden_cases,
            manifest=manifest,
            reports_dir=paths.reports_dir,
            tracker=tracker,
        )
        print(
            json.dumps(
                {
                    "baseline_tfidf_012": cal_summary.baseline_tfidf_012.to_dict(),
                    "best_tfidf": cal_summary.best_tfidf.to_dict(),
                    "best_hybrid": cal_summary.best_hybrid.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "eval":
        golden_cases = _load_golden_cases(paths)
        runner = RAGASBenchmarkRunner(
            medications=meds, chunks=chunks, golden_cases=golden_cases
        )
        eval_results = runner.run_all(
            manifest=manifest,
            reports_dir=paths.reports_dir,
            baselines_dir=paths.baselines_dir,
            tracker=tracker,
        )
        print(
            json.dumps(
                [r.to_dict() for r in eval_results], ensure_ascii=False, indent=2
            )
        )
        return 0

    if args.command == "audit":
        orchestrator = MultiAgentOrchestrator(medications=meds, chunks=chunks)
        guidance = orchestrator.run(
            args.input_text, days_since_emission=args.days_emitted
        )
        print(json.dumps(guidance.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "sync-infosaude":
        client = InfoSaudeLiveClient(gold_dir=paths.gold_dir)
        info_summary = client.sync_from_snapshots_or_live(prefer_live=bool(args.live))
        tracker.log_experiment_run(
            run_name="SPEC06_InfoSaude_Live_Stock_And_Maps_Sync",
            params={
                "ceaf_resource_key": "a665320c-1f2b-43cd-8380-6d39f535daf9",
                "doc_maps_resource_key": "d77b9ba0-317a-4041-88a0-3241c35384ac",
                "stock_schedule": info_summary.stock_update_schedule,
            },
            metrics={
                "total_ceaf_stock_rows": float(info_summary.total_ceaf_stock_rows),
                "distinct_ceaf_medications": float(
                    info_summary.distinct_ceaf_medications
                ),
                "total_establishments": float(info_summary.total_establishments),
                "geolocated_establishments": float(
                    info_summary.geolocated_establishments
                ),
            },
            tags={
                "spec_id": "SPEC-06",
                "stock_sha256": info_summary.stock_sha256,
                "maps_sha256": info_summary.maps_sha256,
            },
        )
        print(json.dumps(info_summary.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "check-stock":
        client = InfoSaudeLiveClient(gold_dir=paths.gold_dir)
        stock_matches = client.query_medication_stock(args.medication)
        ra_pharmacies = client.find_pharmacies_by_ra(args.ra, top_k=5)
        print(
            json.dumps(
                {
                    "medication_query": args.medication,
                    "ra_query": args.ra,
                    "ceaf_stock_matches": [m.to_dict() for m in stock_matches],
                    "pharmacies_in_ra": [p.to_dict() for p in ra_pharmacies],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "index-chroma":
        manager = ChromaVectorStoreManager(vectorstore_dir=paths.data_dir / "vectorstore")
        summary = manager.index_all(paths)
        tracker.log_experiment_run(
            run_name="SPEC07_ChromaDB_MultiCollection_Indexing",
            params={
                "vectorstore_path": summary.vectorstore_path,
                "collections_count": 3,
            },
            metrics={
                "ceaf_stock_indexed": float(summary.stock_count),
                "df_pharmacies_indexed": float(summary.pharmacies_count),
                "protocols_indexed": float(summary.protocols_count),
                "total_indexed": float(summary.total_indexed),
            },
            tags={
                "spec_id": "SPEC-07",
                "backend": "chromadb_persistent",
            },
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "search-chroma":
        manager = ChromaVectorStoreManager(vectorstore_dir=paths.data_dir / "vectorstore")
        where_filter: dict[str, Any] = {}
        filters: list[dict[str, Any]] = []
        if args.unidade:
            filters.append({"unidade": args.unidade})
        if args.somente_com_estoque:
            filters.append({"tem_estoque": True})

        if len(filters) == 1:
            where_filter = filters[0]
        elif len(filters) > 1:
            where_filter = {"$and": filters}

        hits = manager.search(
            query=args.query,
            collection_name=args.collection,
            where_filter=where_filter if where_filter else None,
            top_k=args.top_k,
        )
        print(json.dumps([h.to_dict() for h in hits], ensure_ascii=False, indent=2))
        return 0

    if args.command == "pipeline-pdf":
        pipeline = UnifiedPDFPipeline(paths)
        summary = pipeline.run()
        manager = ChromaVectorStoreManager(vectorstore_dir=paths.data_dir / "vectorstore")
        n_indexed = manager.index_unified_pdf_chunks(paths.silver_dir / "unified_pdf_chunks.json")
        tracker.log_experiment_run(
            run_name="SPEC08_Unified_PDF_Pipeline_Ingestion",
            params={
                "official_pdfs": summary.official_pdfs_count,
                "converted_pdfs": summary.converted_pdfs_count,
                "total_pdfs": summary.total_pdfs_processed,
            },
            metrics={
                "chunks_extracted": float(summary.total_chunks_extracted),
                "chunks_indexed_chroma": float(n_indexed),
            },
            tags={
                "spec_id": "SPEC-08",
                "backend": "pypdf_reportlab_chromadb",
            },
        )
        res = summary.to_dict()
        res["chroma_indexed_chunks"] = n_indexed
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

