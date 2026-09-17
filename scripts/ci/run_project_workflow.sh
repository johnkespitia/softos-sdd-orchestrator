#!/usr/bin/env bash
set -euo pipefail

WORKFLOW_PATH="${1:?workflow path required}"
TARGET_REPOSITORY="${2:?workflow repository required}"
WORKFLOW_REF="${3:?workflow ref required}"
SOURCE_SHA="${4:?source sha required}"
INPUTS_JSON="${5-}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh is required to dispatch project workflows." >&2
  exit 2
fi

if [[ -z "$WORKFLOW_PATH" ]]; then
  echo "workflow path is empty" >&2
  exit 2
fi

if [[ "$WORKFLOW_REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "workflow ref must be a branch or tag, not a commit SHA" >&2
  exit 2
fi

if [[ ! "$SOURCE_SHA" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "source SHA must be a full commit SHA" >&2
  exit 2
fi

INPUT_LINES="$(
  python3 - "$INPUTS_JSON" "${SOURCE_SHA,,}" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1]) if sys.argv[1] not in {"", "null"} else {}
if not isinstance(payload, dict):
    payload = {}
payload["source_sha"] = sys.argv[2]
for key, value in payload.items():
    print(f"{key}={value}")
PY
)"
mapfile -t EXTRA_INPUTS <<< "$INPUT_LINES"

START_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

CMD=(gh workflow run "$WORKFLOW_PATH" --repo "$TARGET_REPOSITORY" --ref "$WORKFLOW_REF")
for item in "${EXTRA_INPUTS[@]}"; do
  CMD+=(-f "$item")
done
"${CMD[@]}"

RUN_ID=""
for _attempt in $(seq 1 30); do
  RUN_ID="$(gh run list \
    --repo "$TARGET_REPOSITORY" \
    --workflow "$WORKFLOW_PATH" \
    --event workflow_dispatch \
    --branch "$WORKFLOW_REF" \
    --created ">=$START_TS" \
    --json databaseId,displayTitle \
    --limit 20 \
    --jq "[.[] | select(.displayTitle | contains(\"${SOURCE_SHA,,}\"))][0].databaseId // empty" || true)"
  if [[ -n "$RUN_ID" ]]; then
    break
  fi
  sleep 5
done

if [[ -z "$RUN_ID" ]]; then
  echo "Could not discover dispatched run for $WORKFLOW_PATH on $TARGET_REPOSITORY." >&2
  exit 1
fi

gh run watch "$RUN_ID" --repo "$TARGET_REPOSITORY" --exit-status
