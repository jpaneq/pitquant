.PHONY: install lint type test pit pg pg-local ci migrate demo docs

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
pg:           ## strict PostgreSQL suite (needs PITQUANT_PG_URL)
	PITQUANT_REQUIRE_POSTGRES=1 pytest -m postgres -rA
pg-local:     ## strict PostgreSQL suite on an embedded PG 16 (no Docker; needs .[localpg])
	python scripts/local_pg.py
ci:           ## local equivalent of .github/workflows/ci.yml (except the docker build)
	$(MAKE) lint type
	pytest -m "pit and not postgres" -rs -p no:warnings > .pit.log || (cat .pit.log; exit 1)
	tail -1 .pit.log; ! grep -E "^SKIPPED" .pit.log
	pytest -m "not postgres"
	$(MAKE) pg-local
