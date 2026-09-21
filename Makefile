.PHONY: validate test reference-p1 prove

validate:
	python scripts/validate_repo.py

test: validate
	python -m unittest discover -s tests -v

reference-p1: test
	python scripts/run_p1_reference.py

prove: reference-p1
	git fsck --full
	@echo "STEWARD_PROOF=PASS"
