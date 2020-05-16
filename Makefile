MODULE := gxmpp

ALL_PY_FILES = $(shell git ls-files -cm --others --exclude-standard | grep -i '\.py$$')
DIFF_PY_FILES = $(shell git diff --diff-filter=ACMRTU --name-only HEAD | grep -i '\.py$$')

DO_DIFFONLY ?= 1
DO_COV ?= 0
COV_REPORT ?= html

TESTFLAGS ?=

ifeq ($(DO_COV), 1)
	TESTFLAGS += --cov=$(MODULE) --cov-report=$(COV_REPORT)
endif

ifeq ($(DO_DIFFONLY), 1)
	PY_FILES = $(DIFF_PY_FILES)
else
	PY_FILES = $(ALL_PY_FILES)
endif

.PHONY: lint
lint:
	flake8 $(PY_FILES)

.PHONY: test
format:
	black -q $(PY_FILES)
	isort -y $(PY_FILES)

.PHONY: test
test:
	python3 -mgevent.monkey --module pytest $(TESTFLAGS)
