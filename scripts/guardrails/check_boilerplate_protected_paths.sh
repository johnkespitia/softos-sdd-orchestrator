#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(pwd)}"
cd "$ROOT_DIR"

if [[ "${ALLOW_BOILERPLATE_CORE_CHANGES:-0}" == "1" ]]; then
  echo "Boilerplate guardrail bypassed by ALLOW_BOILERPLATE_CORE_CHANGES=1"
  exit 0
fi

if [[ "${ENFORCE_BOILERPLATE_GUARDRAILS:-0}" != "1" ]] && [[ -f workspace.config.json ]]; then
  ROOT_REPO="$(python3 - <<'PY'
import json
from pathlib import Path
try:
    payload = json.loads(Path("workspace.config.json").read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(str(payload.get("project", {}).get("root_repo", "")).strip())
PY
)"
  if [[ "$ROOT_REPO" == "sdd-workspace-boilerplate" ]]; then
    echo "Boilerplate guardrail skipped in source workspace (set ENFORCE_BOILERPLATE_GUARDRAILS=1 to enforce)."
    exit 0
  fi
fi

MODE="staged"
BASE_SHA=""
HEAD_SHA=""

usage() {
  cat <<USAGE
Usage:
  scripts/guardrails/check_boilerplate_protected_paths.sh --staged
  scripts/guardrails/check_boilerplate_protected_paths.sh --base <sha> --head <sha>

Env override:
  ALLOW_BOILERPLATE_CORE_CHANGES=1  Bypass this guardrail intentionally.
  ENFORCE_BOILERPLATE_GUARDRAILS=1  Enforce even in source workspace.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --staged)
      MODE="staged"
      shift
      ;;
    --base)
      MODE="range"
      BASE_SHA="${2:-}"
      shift 2
      ;;
    --head)
      MODE="range"
      HEAD_SHA="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" == "range" ]] && { [[ -z "$BASE_SHA" ]] || [[ -z "$HEAD_SHA" ]]; }; then
  echo "--base and --head are required together." >&2
  usage >&2
  exit 2
fi

PROTECTED_LIST="scripts/guardrails/boilerplate_protected_paths.txt"

if [[ ! -f "$PROTECTED_LIST" ]]; then
  echo "Missing $PROTECTED_LIST" >&2
  exit 2
fi

# Capture command output into a variable before splitting it. A process
# substitution (< <(...)) never propagates the inner exit status to the parent,
# so under `set -e` a failed `rg`/`git diff` used to leave the array empty and
# the guardrail silently passed with zero patterns checked.
CHANGED_OUTPUT=""
if [[ "$MODE" == "staged" ]]; then
  if ! CHANGED_OUTPUT="$(git diff --cached --name-only --diff-filter=ACMR)"; then
    echo "Guardrail: failed to list staged files." >&2
    exit 2
  fi
else
  if ! CHANGED_OUTPUT="$(git diff --name-only --diff-filter=ACMR "$BASE_SHA" "$HEAD_SHA")"; then
    echo "Guardrail: failed to list changed files for range $BASE_SHA..$HEAD_SHA." >&2
    exit 2
  fi
fi

mapfile -t CHANGED_FILES <<< "$CHANGED_OUTPUT"

if [[ ${#CHANGED_FILES[@]} -eq 0 || -z "${CHANGED_FILES[0]}" ]]; then
  exit 0
fi

RAW_PATTERNS=""
if ! RAW_PATTERNS="$(sed -e 's/[[:space:]]*$//' "$PROTECTED_LIST")"; then
  echo "Guardrail: failed to read $PROTECTED_LIST." >&2
  exit 2
fi

# Prefer `rg`, fall back to `grep -E` where ripgrep is not installed (the
# devcontainer image ships without it). Both filters are invoked for their
# output only, so a non-zero "no match" status must not abort the script.
PATTERN_OUTPUT=""
if command -v rg >/dev/null 2>&1; then
  PATTERN_OUTPUT="$(printf '%s\n' "$RAW_PATTERNS" | rg -v '^[[:space:]]*(#|$)')" || true
elif command -v grep >/dev/null 2>&1; then
  PATTERN_OUTPUT="$(printf '%s\n' "$RAW_PATTERNS" | grep -v -E '^[[:space:]]*(#|$)')" || true
else
  echo "Guardrail: neither rg nor grep is available to read $PROTECTED_LIST." >&2
  exit 2
fi

mapfile -t PATTERNS <<< "$PATTERN_OUTPUT"

if [[ ${#PATTERNS[@]} -eq 0 || -z "${PATTERNS[0]}" ]]; then
  echo "Guardrail: resolved 0 protected-path patterns from $PROTECTED_LIST" >&2
  echo "Guardrail: the filter is unavailable or the list is empty; refusing to pass vacuously." >&2
  exit 2
fi

VIOLATIONS=()
for file in "${CHANGED_FILES[@]}"; do
  for pattern in "${PATTERNS[@]}"; do
    if [[ "$file" == $pattern ]]; then
      VIOLATIONS+=("$file")
      break
    fi
  done
done

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
  exit 0
fi

printf '%s\n' "Guardrail: detected changes in boilerplate-protected files:" >&2
printf ' - %s\n' "${VIOLATIONS[@]}" >&2
cat >&2 <<'EOM'

If this change is intentional (boilerplate maintenance), rerun with:
  ALLOW_BOILERPLATE_CORE_CHANGES=1

Otherwise, move implementation changes to project/spec paths (for example `projects/**`, `specs/features/**`).
EOM

exit 1
