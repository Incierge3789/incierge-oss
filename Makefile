PYTHON ?= python3

.PHONY: help setup install-hooks scan check test demo

help:
	@echo "setup          copy the example literal list into place (one time)"
	@echo "install-hooks  point git at scripts/hooks/ (content guard + push guard)"
	@echo "scan           run the forensic content scan over every tracked file"
	@echo "check          run every gate once (scan, controls, schemas)"
	@echo "test           run the test suite, including the positive controls"
	@echo "demo           the minimal working example"

setup:
	@if [ -f config/literals.json ]; then \
	    echo "config/literals.json already exists; leaving it alone"; \
	else \
	    cp config/literals.example.json config/literals.json; \
	    echo "config/literals.json created from the example (fictional entries)"; \
	fi

install-hooks:
	git config core.hooksPath scripts/hooks
	@echo "core.hooksPath -> scripts/hooks"

scan:
	$(PYTHON) scripts/scan_forensic.py --all

check:
	$(PYTHON) scripts/scan_forensic.py --all
	$(PYTHON) scripts/control_selfcheck.py
	$(PYTHON) scripts/ledger_gate.py --type negative_result --file ledger/negative_results.jsonl
	$(PYTHON) scripts/ledger_gate.py --type prereg --file examples/prereg.sample.json
	$(PYTHON) scripts/tautological_control_gate.py --audit

test:
	$(PYTHON) scripts/run_tests.py

demo:
	sh examples/minimal/run.sh
