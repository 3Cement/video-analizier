.PHONY: install test run format

install:
	pip install -r requirements.txt
	pip install -e .

test:
	PYTHONPATH=backend pytest -q

run:
	PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

format:
	python -m compileall backend/app
