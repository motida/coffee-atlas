#!/usr/bin/env bash
#
# Push Coffee Atlas to two Hugging Face Spaces (api + web).
#
# Prereqs (do these once, manually, on huggingface.co):
#   1. Create a Space named "coffee-atlas-api"  (SDK: Docker, hardware: CPU basic)
#   2. Create a Space named "coffee-atlas-web"  (SDK: Docker, hardware: CPU basic)
#   3. On the api Space → Settings → Variables and secrets:
#        GEMINI_API_KEY  (secret) — only needed if you re-run embeddings on the Space
#   4. On the web Space → Settings → Variables and secrets:
#        BACKEND_URL  (variable) = https://<HF_USER>-coffee-atlas-api.hf.space
#   5. Install git-lfs locally:  brew install git-lfs && git lfs install
#   6. Authenticate to HF:        hf auth login           (requires a write token;
#                                 install with `pip install -U "huggingface_hub[cli]"`)
#
# Usage:
#   HF_USER=your-username ./deploy/huggingface/deploy.sh           # both Spaces
#   HF_USER=your-username ./deploy/huggingface/deploy.sh api       # backend only
#   HF_USER=your-username ./deploy/huggingface/deploy.sh web       # frontend only
#
set -euo pipefail

: "${HF_USER:?Set HF_USER to your Hugging Face username}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_DIR="$REPO_ROOT/deploy/huggingface"
STAGING_DIR="$DEPLOY_DIR/.staging"
TARGET="${1:-both}"

API_SPACE="coffee-atlas-api"
WEB_SPACE="coffee-atlas-web"
API_URL="https://huggingface.co/spaces/$HF_USER/$API_SPACE"
WEB_URL="https://huggingface.co/spaces/$HF_USER/$WEB_SPACE"

DB_FILE="$REPO_ROOT/data/coffee_atlas.duckdb"

mkdir -p "$STAGING_DIR"

deploy_api() {
    echo "==> Deploying $API_SPACE"

    if [[ ! -f "$DB_FILE" ]]; then
        echo "ERROR: $DB_FILE not found." >&2
        echo "Run the ingest pipeline locally first:" >&2
        echo "  uv run -m backend.ingest.pipeline --all" >&2
        exit 1
    fi

    local stage="$STAGING_DIR/api"
    if [[ ! -d "$stage/.git" ]]; then
        rm -rf "$stage"
        git clone "$API_URL" "$stage"
    fi

    pushd "$stage" >/dev/null
    git lfs install --local
    popd >/dev/null

    rsync -a --delete \
        --exclude '.git/' \
        --exclude '.gitattributes' \
        --exclude 'README.md' \
        --exclude 'Dockerfile' \
        --exclude '__pycache__/' \
        --exclude '*.pyc' \
        --exclude '.pytest_cache/' \
        "$REPO_ROOT/backend/"   "$stage/backend/"
    rsync -a --delete \
        --exclude '.git/' \
        --exclude '__pycache__/' \
        "$REPO_ROOT/ontology/"  "$stage/ontology/"
    cp "$REPO_ROOT/pyproject.toml" "$stage/pyproject.toml"
    cp "$REPO_ROOT/uv.lock"        "$stage/uv.lock"

    cp "$DEPLOY_DIR/api/Dockerfile"      "$stage/Dockerfile"
    cp "$DEPLOY_DIR/api/README.md"       "$stage/README.md"
    cp "$DEPLOY_DIR/api/.gitattributes"  "$stage/.gitattributes"

    mkdir -p "$stage/data"
    cp "$DB_FILE" "$stage/data/coffee_atlas.duckdb"

    pushd "$stage" >/dev/null
    git add -A
    if git diff --cached --quiet; then
        echo "    (no changes)"
    else
        git commit -m "Deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        git push
    fi
    popd >/dev/null
}

deploy_web() {
    echo "==> Deploying $WEB_SPACE"

    local stage="$STAGING_DIR/web"
    if [[ ! -d "$stage/.git" ]]; then
        rm -rf "$stage"
        git clone "$WEB_URL" "$stage"
    fi

    rsync -a --delete \
        --exclude '.git/' \
        --exclude 'README.md' \
        --exclude 'Dockerfile' \
        --exclude 'node_modules/' \
        --exclude '.next/' \
        --exclude '*.tsbuildinfo' \
        "$REPO_ROOT/frontend/" "$stage/frontend/"

    cp "$DEPLOY_DIR/web/Dockerfile" "$stage/Dockerfile"
    cp "$DEPLOY_DIR/web/README.md"  "$stage/README.md"

    pushd "$stage" >/dev/null
    git add -A
    if git diff --cached --quiet; then
        echo "    (no changes)"
    else
        git commit -m "Deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        git push
    fi
    popd >/dev/null
}

case "$TARGET" in
    api)  deploy_api ;;
    web)  deploy_web ;;
    both) deploy_api; deploy_web ;;
    *)    echo "Unknown target: $TARGET (use api | web | both)" >&2; exit 2 ;;
esac

echo
echo "Done. Spaces will rebuild automatically. Watch the logs at:"
echo "  $API_URL"
echo "  $WEB_URL"
