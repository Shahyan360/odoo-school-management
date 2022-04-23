# Publication safety report

Publication explicitly authorized by the user on 2026-10-28.
Implementation author: Muhammad Shahyan Khalid. Each project has a separate Git repository.

## Publication scope

Only independently authored addon code, fictional fixtures, deployment scripts, documentation
and reviewed demonstration media are selected. Employer files and history were not used.
The parent workspace and private runtime remain outside this repository.

## Publication checks

- Exact independent Git root checked: `06-LAPS-School-ERP`.
- Candidate files scanned: 32. Content-pattern findings: 0.
- Symlinks/reparse points: 0. Nested repositories are rejected.
- Patterns cover private keys, known provider keys, credential URLs and literal credentials.
- Source review considered fictional identifiers, public provider endpoints and private environment configuration.
- No binary demonstration media is included.
- A heuristic scan is supplemental to source and media review; it is not proof of absence of secrets.

## Exclusions

Private .env/.local contents, passwords, database/filestore data, runtime downloads, caches,
logs, archives, private keys and binaries remain excluded by the publication set and .gitignore.
No original employer code, client database or production record is included.

## Licenses and dependencies

New addon source is LGPL-3; the included license text applies. Public Odoo Community is an
external dependency. No Enterprise/commercial addon or runtime image is redistributed.
Referenced images, Python dependencies and official schema assets retain upstream terms.
Official PINT schema/rule assets are user-supplied private dependencies, not bundled files.

## Validation scope

Implementation and runtime validation are recorded separately. See docs/VERIFICATION.md.
Publication scanning does not execute business workflows, tests, providers or Docker builds.

## Published file inventory

- `.env.example`
- `.gitignore`
- `LICENSE`
- `README.md`
- `addons/school_operations/__init__.py`
- `addons/school_operations/__manifest__.py`
- `addons/school_operations/common.py`
- `addons/school_operations/controllers/__init__.py`
- `addons/school_operations/controllers/bank.py`
- `addons/school_operations/controllers/main.py`
- `addons/school_operations/data/cron.xml`
- `addons/school_operations/data/sequence.xml`
- `addons/school_operations/demo/fixtures.xml`
- `addons/school_operations/models/__init__.py`
- `addons/school_operations/models/bank.py`
- `addons/school_operations/models/operations.py`
- `addons/school_operations/reports/summary.xml`
- `addons/school_operations/security/campus.xml`
- `addons/school_operations/security/groups.xml`
- `addons/school_operations/security/ir.model.access.csv`
- `addons/school_operations/security/rules.xml`
- `addons/school_operations/views/account.xml`
- `addons/school_operations/views/operations.xml`
- `docker/compose.yaml`
- `docker/images.lock.json`
- `docs/FEATURES.md`
- `docs/VERIFICATION.md`
- `scripts/bootstrap.py`
- `scripts/lab.ps1`
- `scripts/publication_audit.py`
- `scripts/seed.py`
- `scripts/simulate_bank.py`
- `PUBLICATION_SAFETY_REPORT.md` (excluded from its own recursive hash).
- `docs/publication-inventory.json` (excluded from its own recursive hash).

## Findings

No content-pattern, link, nested-repository or stale-status findings in the selected publication files.
