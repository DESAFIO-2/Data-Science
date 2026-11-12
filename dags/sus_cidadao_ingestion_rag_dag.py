"""DAG do Apache Airflow: Ingestão InfoSaúde-DF, PDFs Oficiais e Indexação ChromaDB.

Sincroniza automaticamente os dados em tempo real da API do Power BI (SES-DF),
converte JSONs em relatórios PDF padronizados, extrai chunks dos normativos oficiais
(RENAME 2024, REME-DF, PFPB, HUB-UnB) e atualiza a base vetorial ChromaDB.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_ROOT = os.environ.get(
    "SUS_CIDADAO_DS_ROOT",
    str(Path(__file__).resolve().parents[1]),
)

default_args = {
    "owner": "sus-cidadao-ds",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="sus_cidadao_ingestion_rag_pipeline",
    default_args=default_args,
    description="Pipeline diário de coleta InfoSaúde-DF, geração JSON->PDF e atualização vetorial no ChromaDB",
    schedule="30 9,18 * * 1-5",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    tags=["sus-cidadao", "rag", "chromadb", "infosaude"],
) as dag:
    sync_infosaude_live = BashOperator(
        task_id="sync_infosaude_live",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli sync-infosaude --live"
        ),
    )

    sync_canonical_catalog = BashOperator(
        task_id="sync_canonical_catalog",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli sync"
        ),
    )

    run_unified_pdf_pipeline = BashOperator(
        task_id="run_unified_pdf_pipeline",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli pipeline-pdf"
        ),
    )

    index_chroma_collections = BashOperator(
        task_id="index_chroma_collections",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli index-chroma"
        ),
    )

    (
        sync_infosaude_live
        >> sync_canonical_catalog
        >> run_unified_pdf_pipeline
        >> index_chroma_collections
    )

