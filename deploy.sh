#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

DEPLOY_PATH="${DEPLOY_PATH:-$SCRIPT_DIR}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
SYSTEMD_SERVICE="${SYSTEMD_SERVICE:-indiainnovates-automation}"
INSTANCE_COUNT="${INSTANCE_COUNT:-1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements.txt}"

if [[ ! -d "$DEPLOY_PATH/.git" ]]; then
  echo "Repository not found at $DEPLOY_PATH" >&2
  exit 1
fi

cd "$DEPLOY_PATH"

if [[ "$VENV_DIR" == ".venv" && ! -d "$VENV_DIR" && -d "venv" ]]; then
  VENV_DIR="venv"
fi

echo "==> Syncing branch $DEPLOY_BRANCH"
git fetch --prune origin
git checkout "$DEPLOY_BRANCH"
git reset --hard "origin/$DEPLOY_BRANCH"

echo "==> Ensuring virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip

if [[ -f "$REQUIREMENTS_FILE" ]]; then
  echo "==> Installing Python dependencies"
  python -m pip install -r "$REQUIREMENTS_FILE"
fi

echo "==> Restarting service instances"
# Streamlit file uploads depend on process-local session state, so
# running a single backend instance is the safe default.
for i in $(seq 1 "$INSTANCE_COUNT"); do
  sudo systemctl restart "${SYSTEMD_SERVICE}@${i}"
done

# Check if at least one instance is active
if sudo systemctl is-active --quiet "${SYSTEMD_SERVICE}@1"; then
  echo "==> Services are running"
else
  echo "==> Warning: Service check failed" >&2
fi

echo "==> Deploy complete"
