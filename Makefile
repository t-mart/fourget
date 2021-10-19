src-dirs = fourget tests

.PHONY: all
all: pydocstyle isort black flake8 pylint mypy test

.PHONY: mypy
mypy:
	mypy $(src-dirs)

.PHONY: isort
isort:
	isort $(src-dirs)

.PHONY: flake8
flake8:
	flake8 $(src-dirs)

.PHONY: pylint
pylint:
	pylint $(src-dirs)

.PHONY: black
black:
	black $(src-dirs)

.PHONY: pydocstyle
pydocstyle:
	pydocstyle $(src-dirs)

.PHONY: test
test:
	pytest tests --cov=fourget --cov-report=xml

.PHONY: pip-compile
pip-compile:
	pip-compile ci/poetry-requirements.in
