"""Recreate the Hugging Face api Space and restore all its secrets in one shot.

Recreating a Space (delete + create) is the reliable way to reset its Git-LFS
storage when the ~1 GB free-tier cap fills — see DEPLOY.md, "Resetting the LFS
storage quota". But a fresh Space starts with **zero** secrets, and the api
Space needs three at runtime: ``GEMINI_API_KEY``, ``DATABASE_URL``, and
``JWT_SECRET``. Forgetting the auth pair fails silently and partially (content
endpoints stay 200 while every ``/auth/*`` and ``/account/*`` route 503s) — the
exact outage this script exists to prevent. It re-adds all three programmatically
from the local environment right after creating the Space, so they can never be
forgotten, then runs ``deploy.sh api`` to push code + DB into the empty Space.

The guard refuses to delete anything unless all three secrets are present
locally, so you can never recreate into a half-configured Space.

Usage (from the repo root):
    # dry run — validates secrets + prints the plan, changes nothing, no extra deps:
    HF_USER=<user> uv run python deploy/huggingface/recreate_api_space.py

    # actually delete + recreate + restore secrets + deploy:
    HF_USER=<user> uv run --with huggingface_hub python deploy/huggingface/recreate_api_space.py --yes

Auth: uses HF_TOKEN if set, otherwise your stored ``hf auth login`` credentials.
The token needs write access to the Space.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from backend.config import settings

API_SPACE = "coffee-atlas-api"

# The secrets the api Space needs at runtime, sourced from the local environment
# (.env, via backend.config.settings). Keep in sync with DEPLOY.md §4.
REQUIRED_SECRETS = ("GEMINI_API_KEY", "DATABASE_URL", "JWT_SECRET")

REPO_ROOT = Path(__file__).resolve().parents[2]


def collect_secrets() -> dict[str, str]:
    """Return ``{name: value}`` for the required secrets from local settings."""
    return {name: getattr(settings, name, "") or "" for name in REQUIRED_SECRETS}


def missing_secrets(secrets: dict[str, str]) -> list[str]:
    """Names of required secrets that are absent/empty locally (in declared order)."""
    return [name for name in REQUIRED_SECRETS if not secrets.get(name)]


def _print_plan(repo_id: str) -> None:
    print("\nDRY RUN — nothing changed. Re-run with --yes to:")
    print(f"  1. delete  space {repo_id}")
    print(f"  2. create  space {repo_id} (docker sdk, public)")
    print(
        f"  3. re-add  {len(REQUIRED_SECRETS)} secrets from local .env "
        f"({', '.join(REQUIRED_SECRETS)})"
    )
    print("  4. deploy  code + DB via deploy.sh api")
    print("\nThe --yes run needs huggingface_hub:")
    print("  uv run --with huggingface_hub python deploy/huggingface/recreate_api_space.py --yes")


def _recreate(repo_id: str, secrets: dict[str, str]) -> None:
    """Delete + recreate the Space and restore its secrets (destructive)."""
    # Imported late so the dry run and the secret guard work in the plain project
    # venv, without `--with huggingface_hub`. Done before any destructive call so
    # a missing dependency fails safely, with the Space still intact.
    try:
        from huggingface_hub import HfApi
        from huggingface_hub.utils import RepositoryNotFoundError
    except ImportError:
        sys.exit(
            "ERROR: huggingface_hub is required for --yes. Re-run with:\n"
            "  uv run --with huggingface_hub python "
            "deploy/huggingface/recreate_api_space.py --yes"
        )

    api = HfApi(token=os.environ.get("HF_TOKEN"))

    print(f"==> Deleting space {repo_id} ...")
    try:
        api.delete_repo(repo_id=repo_id, repo_type="space")
    except RepositoryNotFoundError:
        print("    (did not exist — creating fresh)")

    print(f"==> Creating space {repo_id} ...")
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", private=False)

    print("==> Restoring secrets ...")
    for name, value in secrets.items():
        api.add_space_secret(repo_id=repo_id, key=name, value=value)
        print(f"    set {name}")


def _deploy(hf_user: str) -> int:
    """Push code + DB into the now-empty Space via deploy.sh."""
    # Force a fresh clone of the recreated (empty) Space: the old staging dir
    # still points at the deleted repo's history.
    staging = REPO_ROOT / "deploy/huggingface/.staging/api"
    if staging.exists():
        shutil.rmtree(staging)
    print("==> Deploying code + DB via deploy.sh ...")
    return subprocess.run(
        ["bash", str(REPO_ROOT / "deploy/huggingface/deploy.sh"), "api"],
        cwd=REPO_ROOT,
        env={**os.environ, "HF_USER": hf_user},
        check=False,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--yes", action="store_true", help="actually delete + recreate (default: dry run)"
    )
    parser.add_argument(
        "--skip-deploy", action="store_true", help="recreate + set secrets but skip deploy.sh"
    )
    args = parser.parse_args(argv)

    hf_user = os.environ.get("HF_USER")
    if not hf_user:
        print("ERROR: set HF_USER to your Hugging Face username.", file=sys.stderr)
        return 2
    repo_id = f"{hf_user}/{API_SPACE}"

    secrets = collect_secrets()
    missing = missing_secrets(secrets)
    if missing:
        # Guard: never delete a Space we can't fully reconfigure afterwards.
        print(
            "ERROR: refusing to recreate — required secrets are missing from the "
            f"local environment (.env): {', '.join(missing)}.\n"
            "Set them locally first; recreating without them would leave the Space "
            "with silently broken auth (the exact failure this script prevents).",
            file=sys.stderr,
        )
        return 1

    print(f"Target Space:       {repo_id}")
    print(f"Secrets to restore: {', '.join(REQUIRED_SECRETS)} (all present locally)")

    if not args.yes:
        _print_plan(repo_id)
        return 0

    _recreate(repo_id, secrets)

    if args.skip_deploy:
        print("\n--skip-deploy: secrets set, code/DB not pushed. Deploy with:")
        print(
            f"  rm -rf deploy/huggingface/.staging/api && "
            f"HF_USER={hf_user} ./deploy/huggingface/deploy.sh api"
        )
        return 0

    return _deploy(hf_user)


if __name__ == "__main__":
    raise SystemExit(main())
