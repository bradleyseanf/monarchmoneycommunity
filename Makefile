builddist:
	python setup.py check
	python setup.py sdist
	python setup.py bdist_wheel --universal

install:
	pip install .

.PHONY: docs docs-build
docs:
	python -m mkdocs serve

docs-build:
	python -m mkdocs build --strict

twine:
	twine upload dist/monarchmoney*

uninstall:
	pip uninstall monarchmoney

clean:
	rm -fR build dist monarchmoney.egg-info monarchmoney/__pycache__ *.json
