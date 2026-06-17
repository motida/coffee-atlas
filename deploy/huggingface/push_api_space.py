"""Push the api Space's code to Hugging Face — code only, never the DB.

Used by the CI deploy job (.github/workflows/ci.yml). Expects ``$STAGE`` to
point at a pre-assembled Space layout (backend/, ontology/, and the root files
pyproject.toml / uv.lock / Dockerfile / README.md / .gitattributes) that does
NOT contain ``data/``. The upload replaces those code paths on the Space but
leaves everything else — crucially ``data/coffee_atlas.duckdb``, the bundled
DuckDB that is built locally and deployed manually via ``deploy.sh`` — in place.

This is the continuous-delivery counterpart to ``deploy.sh``: that script ships
code *and* a freshly built DB from a workstation; this ships only code on every
push to main, so data changes still go through ``deploy.sh`` deliberately.

Env vars:
  HF_TOKEN       Hugging Face write token.
  HF_API_SPACE   Space repo id, e.g. "motidav/coffee-atlas-api".
  STAGE          Path to the assembled Space layout (no data/).
  GITHUB_SHA     Optional; used to label the commit.
"""

from __future__ import annotations

import os

from huggingface_hub import HfApi

# Code paths the Space owns. Listed as delete_patterns so stale files (e.g. a
# renamed/removed module) are pruned, then re-added from STAGE. Deliberately
# omits data/** so the bundled DuckDB is never touched.
CODE_PATHS = [
    "backend/**",
    "ontology/**",
    "Dockerfile",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    ".gitattributes",
]


def main() -> None:
    space = os.environ["HF_API_SPACE"]
    stage = os.environ["STAGE"]
    sha = os.environ.get("GITHUB_SHA", "")[:7]

    HfApi(token=os.environ["HF_TOKEN"]).upload_folder(
        repo_id=space,
        repo_type="space",
        folder_path=stage,
        commit_message=f"CI deploy {sha}".strip(),
        ignore_patterns=["**/__pycache__/**", "**/*.pyc", "**/.pytest_cache/**"],
        delete_patterns=CODE_PATHS,
    )
    print(f"Deployed code to Space {space} (data/ left untouched)")


if __name__ == "__main__":
    main()
