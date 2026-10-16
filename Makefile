.PHONY: build check examples package clean
REPOSITORY ?= OWNER/flatcar-wings
TAG ?= v$(shell cat VERSION)

build:
	bash scripts/build.sh amd64
	bash scripts/build.sh arm64

check:
	bash scripts/check.sh

examples:
	python3 scripts/make-examples.py --repository '$(REPOSITORY)' --tag '$(TAG)'

package:
	python3 scripts/package.py --repository '$(REPOSITORY)' --tag '$(TAG)'
	python3 tests/verify_release.py

clean:
	rm -rf dist release
