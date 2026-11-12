"""DAG do Apache Airflow: Avaliação Científica RAGAS, Calibração e Validação Multiagentes (LangGraph).

Orquestra semanalmente o perfilamento EDA, a calibração do limiar de abstenção (`min_score`),
o benchmark comparativo RAGAS sobre a base vetorial ChromaDB e a verificação ponta a ponta
dos agentes LangGraph com guardrails LGPD e CFM.
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
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="sus_cidadao_agents_eval_pipeline",
    default_args=default_args,
    description="Avaliação semanal RAGAS, calibração de recuperadores e smoke test dos agentes LangGraph",
    schedule="0 8 * * 1",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    tags=["sus-cidadao", "ragas", "langgraph", "agents"],
) as dag:
    run_eda_profiling = BashOperator(
        task_id="run_eda_profiling",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli eda"
        ),
    )

    calibrate_thresholds = BashOperator(
        task_id="calibrate_thresholds",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli calibrate"
        ),
    )

    run_ragas_benchmark = BashOperator(
        task_id="run_ragas_benchmark",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "PYTHONPATH=src python -m sus_cidadao_ds.cli eval"
        ),
    )

    smoke_test_langgraph_agents = BashOperator(
        task_id="smoke_test_langgraph_agents",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            'PYTHONPATH=src python -m sus_cidadao_ds.cli audit '
            '"Receita médica: Losartana potássica 50 mg e Adalimumabe 40 mg. Moro em Ceilândia - DF."'
        ),
    )

    (
        run_eda_profiling
        >> calibrate_thresholds
        >> run_ragas_benchmark
        >> smoke_test_langgraph_agents
    )

