PY ?= python3
WEB := apps/web
API := services/api
WORKER := services/worker

.PHONY: help api-install worker-install web-install install \
        demo web-dev worker-dev sample-splat \
        test test-python test-web lint lint-python lint-web compose-up

help:
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: api-install worker-install web-install ## Install everything

api-install: ## Install API deps (editable, with dev extras)
	$(PY) -m pip install -e '$(API)[dev]'

worker-install: ## Install worker deps (editable, with dev extras; CPU-only)
	$(PY) -m pip install -e '$(WORKER)[dev]'

web-install: ## Install web deps
	cd $(WEB) && npm install

demo: ## Run API on :8000 with inline mock pipeline + local storage (zero services)
	cd $(API) && STORAGE_BACKEND=local JOB_TRIGGER=inline PIPELINE_MODE=mock \
		$(PY) -m uvicorn spatialscan_api.main:app --host 0.0.0.0 --port 8000

web-dev: ## Run web dev server on :5173 (proxies /api + /media to :8000)
	cd $(WEB) && npm run dev

worker-dev: ## Run the Redis queue worker (requires redis; PIPELINE_MODE from env)
	$(PY) -m spatialscan_worker.queue_worker

sample-splat: ## Regenerate apps/web/public/sample.splat
	$(PY) scripts/generate_sample_splat.py

test: test-python test-web ## Run all tests

test-python: ## pytest for api + worker
	$(PY) -m pytest $(WORKER)/tests $(API)/tests -q

test-web: ## vitest + production build
	cd $(WEB) && npm run test -- --run && npm run build

lint: lint-python lint-web ## Lint everything

lint-python: ## ruff over both python services
	$(PY) -m ruff check $(API) $(WORKER) scripts

lint-web: ## eslint + tsc
	cd $(WEB) && npm run lint

compose-up: ## Full local stack: redis + minio + api + mock worker
	docker compose up --build
