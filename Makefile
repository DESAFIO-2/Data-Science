.PHONY: dev-install sync-data eda calibrate benchmark run-agents index-chroma pipeline-pdf serve test lint clean dag-ingestion dag-eval

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PYTHONPATH := src

dev-install:
	@command -v uv >/dev/null 2>&1 && uv sync --all-extras || (python3 -m venv .venv && .venv/bin/pip install -e ".[dev]")

sync-data:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli sync

eda:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli eda

calibrate:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli calibrate

benchmark:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli eval

run-agents:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli audit "Receita: Losartana potássica 50 mg 1 cp 12/12h, Metformina 500 mg e Adalimumabe 40 mg. Solicito Ecocardiograma Transtorácico. Moro em Ceilândia - DF."

index-chroma:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli index-chroma

pipeline-pdf:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli pipeline-pdf

serve:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli serve --host 127.0.0.1 --port 8000

dag-ingestion:
	@echo "==> Executando DAG [sus_cidadao_ingestion_rag_pipeline]..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli sync-infosaude
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli sync
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli pipeline-pdf
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli index-chroma
	@echo "==> DAG [sus_cidadao_ingestion_rag_pipeline] concluida com sucesso!"

dag-eval:
	@echo "==> Executando DAG [sus_cidadao_agents_eval_pipeline]..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli eda
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli calibrate
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli eval
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m sus_cidadao_ds.cli audit "Receita: Losartana potássica 50 mg 1 cp 12/12h, Metformina 500 mg e Adalimumabe 40 mg. Solicito Ecocardiograma Transtorácico. Moro em Ceilândia - DF."
	@echo "==> DAG [sus_cidadao_agents_eval_pipeline] concluida com sucesso!"

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

lint:
	@command -v uv >/dev/null 2>&1 && (uv run ruff check src tests && uv run mypy src tests) || $(PYTHON) -m compileall -q src tests

clean:
	rm -rf .artifacts .pytest_cache .mypy_cache .ruff_cache


