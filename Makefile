.PHONY: install lint type test pit migrate demo docs

install:      ## dev install
	pip install -e ".[dev]"
lint:
	ruff check src tests migrations scripts && ruff format --check src tests migrations scripts
type:
	mypy
test:
	pytest
pit:          ## only the anti-leakage suite
	pytest -m pit
migrate:
	alembic upgrade head
demo:         ## API on SYNTHETIC data at http://127.0.0.1:8000/docs
	PITQUANT_DEMO=1 uvicorn pitquant.api.main:app --reload
docs:         ## regenerate docs/DATA_MODEL.md from the ORM
	python scripts/gen_data_model_doc.py
