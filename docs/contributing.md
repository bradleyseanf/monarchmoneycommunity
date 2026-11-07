# Documentation

The site is static: a method explorer on the home page, with MkDocs and
mkdocstrings for the supporting guides. The build reads Python and GraphQL source
without importing or logging into the client. There is no application server or
database to operate.

## Preview locally

From the repository root, create a separate environment for the docs:

```sh
python3 -m venv .venv-docs
source .venv-docs/bin/activate
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

On Windows, activate with `.venv-docs\Scripts\activate` instead. Open
<http://127.0.0.1:8000/>. Changes to guides and client source reload the preview.

Validate the production build before opening a pull request:

```sh
python -m mkdocs build --strict
```

The generated files go into `site/`, which is ignored by Git. With the environment
activated, `make docs` and `make docs-build` run the same commands.

## Keep the reference current

- Add or update public methods in the Python client. The method directory and
  class reference pick them up automatically, including undocumented methods.
- Write parameter descriptions in the existing Sphinx docstring style
  (`:param parameter_name: description`). Type hints supply signature types.
- Update the guides in `docs/` when a workflow or response shape changes.
- Request and response examples live in `docs/data/method-examples.json`.
  The explorer also uses existing test fixtures. Keep synthetic examples small
  and label partial responses; do not copy personal account data into them.
- Add newly exported models to `typedmonarchmoney/models.py`; the model reference
  follows that module. Add new standalone reference pages to `mkdocs.yml`.

`scripts/api_catalog.py` generates method signatures, parameters, GraphQL
documents, variable types, selected response fields, and schemas from examples or
typed model definitions. GraphQL queries do not declare response field types:
unknown types stay unknown, and example-derived schemas are labeled as such.
This catalog is available at `assets/api-catalog.json` in the built site.

Check the catalog without contacting Monarch:

```sh
python -m unittest discover -s tests -p test_api_catalog.py -v
```

The build uses the exact source in the checked-out commit, not whichever package
version happens to be on PyPI. Dependencies are pinned in `requirements-docs.txt`
and kept separate from runtime requirements. Existing Dependabot configuration
can propose pip dependency updates on `dev`; review them with the docs build.

## Publishing

The `Documentation` workflow in `.github/workflows/docs.yml`:

1. Tests the catalog and builds with `mkdocs build --strict` on pull requests and pushes to `dev` or
   `main`. Invalid reference targets and broken internal links fail the build.
2. Uploads the static site only for a push or manual run on `main`.
3. Deploys the successful build to the `github-pages` environment using GitHub's
   official Pages actions.

Merge the documentation branch into `dev`, then merge `dev` into `main` to
publish. The existing package-version check still applies when a release includes
changes under `monarchmoney/` or `typedmonarchmoney/`. Later merges to `main`
rebuild and redeploy automatically. Pull requests
and `dev` pushes validate the docs without changing the public site.

Docs deployment is independent of the package release workflow, so a docs-only
change does not require a package version bump to publish the site.
