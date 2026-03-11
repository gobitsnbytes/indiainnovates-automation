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

echo "==> Installing system packages"
sudo apt-get update
sudo apt-get install -y \
  poppler-utils \
  tesseract-ocr \
  libreoffice-impress

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

canonical_service_unit() {
  local service_name="$1"
  if [[ "$service_name" == *.service ]]; then
    printf '%s\n' "$service_name"
  else
    printf '%s.service\n' "$service_name"
  fi
}

service_exists() {
  local unit_name="$1"
  sudo systemctl cat "$unit_name" >/dev/null 2>&1
}

restart_exact_service() {
  local unit_name="$1"
  echo "==> Restarting $unit_name"
  sudo systemctl restart "$unit_name"
  RESTARTED_UNITS+=("$unit_name")
}

restart_service_instances() {
  local service_base="$1"
  local i
  for i in $(seq 1 "$INSTANCE_COUNT"); do
    restart_exact_service "${service_base}@${i}.service"
  done
}

echo "==> Restarting service instances"
# Streamlit file uploads depend on process-local session state, so
# running a single backend instance is the safe default.
declare -a RESTARTED_UNITS=()

SYSTEMD_SERVICE_BASE="${SYSTEMD_SERVICE%.service}"

if [[ "$SYSTEMD_SERVICE_BASE" == *@* ]]; then
  if [[ "$SYSTEMD_SERVICE_BASE" == *@ ]]; then
    restart_service_instances "${SYSTEMD_SERVICE_BASE%@}"
  else
    restart_exact_service "$(canonical_service_unit "$SYSTEMD_SERVICE_BASE")"
  fi
else
  EXACT_UNIT="$(canonical_service_unit "$SYSTEMD_SERVICE_BASE")"
  TEMPLATE_BASE="$SYSTEMD_SERVICE_BASE"

  if service_exists "$EXACT_UNIT"; then
    restart_exact_service "$EXACT_UNIT"
  elif service_exists "${TEMPLATE_BASE}@1.service"; then
    restart_service_instances "$TEMPLATE_BASE"
  else
    echo "Systemd service '$SYSTEMD_SERVICE' not found."
    echo "Set SYSTEMD_SERVICE to either the exact unit (for example: indiainnovates-automation.service)"
    echo "or the template base name (for example: indiainnovates-automation)." 
    exit 1
  fi
fi

# Check if restarted units are active
ALL_ACTIVE=true
for unit_name in "${RESTARTED_UNITS[@]}"; do
  if ! sudo systemctl is-active --quiet "$unit_name"; then
    echo "==> Warning: Service check failed for $unit_name" >&2
    ALL_ACTIVE=false
  fi
done

if [[ "$ALL_ACTIVE" == true ]]; then
  echo "==> Services are running"
else
  echo "==> Warning: One or more services failed health checks" >&2
fi

echo "==> Deploy complete"
