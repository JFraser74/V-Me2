PORT ?= 8080
PY ?= python3

.PHONY: run test smoke install

run:
	# Start the app on the configured PORT (default 8080). Use PYTHONPATH so
	# imports work from the repo root.
	PYTHONPATH=. PORT=$(PORT) uvicorn main:app --host 0.0.0.0 --port $(PORT)

test:
	# Free the configured PORT (default 8080), start a temporary server on it,
	# run unit tests, then clean up the server. This helps in dev/CodeSpace where
	# stray servers may hold the port.
	@echo "Freeing port $(PORT) if in use..."
	@sh -c 'pids=$$(lsof -ti tcp:$(PORT) 2>/dev/null || true); if [ -n "$$pids" ]; then echo "killing $$pids"; echo "$${pids}" | xargs -r kill -9 || true; fi'
	@echo "Starting temporary uvicorn on port $(PORT)..."
	# Allow LANGGRAPH=1 to enable the real LangGraph agent during tests.
	@PYTHONPATH=. PORT=$(PORT) AGENT_USE_LANGGRAPH=$(LANGGRAPH) nohup uvicorn main:app --host 127.0.0.1 --port $(PORT) --log-level warning > /tmp/uvicorn.log 2>&1 & echo $$! > .uvicorn_pid
	@sleep 1
	@echo "Running tests..."
	@PYTHONPATH=. AGENT_USE_LANGGRAPH=$(LANGGRAPH) pytest -q
	@echo "Cleaning up temporary server..."
	@sh -c 'if [ -f .uvicorn_pid ]; then pid=$$(cat .uvicorn_pid); kill -9 $$pid 2>/dev/null || true; rm -f .uvicorn_pid; fi'

smoke:
	# Run the one-file smoke script (starts the app and posts a message).
	PYTHONPATH=. PORT=$(PORT) $(PY) scripts/smoke_agent_post.py

install:
	# Install project dependencies.
	python -m pip install --upgrade pip
	pip install -r requirements.txt
