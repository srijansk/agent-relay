#!/usr/bin/env bash
# Capture a "compounding improvement" demo end-to-end.
#
# Runs `bug-rca-fix` twice in a fresh /tmp directory:
#   Run 1: a config-coercion bug, with intentionally-thin context. The
#          reviewer typically rejects on missing failing-test or vague
#          rollback. We let the loop reach its iteration cap and
#          manually snapshot, so the rejection bullets land in
#          .relay/history/.
#   Distill: produces .relay/LESSONS.md and .relay/lessons.json — real,
#            forward-looking lessons (with --llm) or raw rejection bullets
#            (without --llm).
#   Run 2: a different bug in the same class. The bug-rca-fix planner
#          role has inject_lessons: true, so its prompt now contains the
#          lessons distilled from Run 1. Compare run 2's plan.md to
#          run 1's first plan.md — does run 2 address the things run 1
#          got rejected on, from the start?
#
# Usage:
#   OPENAI_API_KEY=sk-... ./scripts/capture-compounding-demo.sh
#   ANTHROPIC_API_KEY=sk-ant-... PROVIDER=anthropic MODEL=claude-sonnet-4-6 ./scripts/capture-compounding-demo.sh
#
# This script never writes the API key to disk. It reads it from your
# environment, passes it to the relay process, and clears nothing else.
#
# Output: a directory of artifacts at /tmp/relay-compounding-demo/<runid>/
# you can browse to compare the two runs side-by-side.
set -euo pipefail

PROVIDER="${PROVIDER:-openai}"
MODEL="${MODEL:-gpt-4o}"
USE_LLM_DISTILL="${USE_LLM_DISTILL:-1}"
OUT="${OUT:-/tmp/relay-compounding-demo}"

if [ "$PROVIDER" = "openai" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY not set. export it (do not write it to a file) or pass PROVIDER=anthropic." >&2
  exit 1
fi
if [ "$PROVIDER" = "anthropic" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY not set." >&2
  exit 1
fi

command -v relay >/dev/null || { echo "relay not on PATH. pip install -e .[openai,anthropic] from the repo." >&2; exit 1; }

rm -rf "$OUT" && mkdir -p "$OUT" && cd "$OUT"
relay init --template bug-rca-fix >/dev/null
mkdir -p .relay/workflows/default/artifacts

cat > .relay/relay.yml <<EOF
default_workflow: default
backend: $PROVIDER
backend_config:
  model: $MODEL
  temperature: 0.2
  max_tokens: 4000
history:
  enabled: true
EOF

# --- Run 1: thin context to invite rejections -------------------------------
cat > .relay/workflows/default/artifacts/context.md <<'EOF'
# Context

Customers say a date filter on `/v1/orders?since=...` returns
yesterday's orders even when they pass today's date. Suspect timezone
handling.

- `src/api/orders.py` parses the `since` query param and queries the DB.
EOF

echo "==> Run 1: bug A (timezone), thin context — expect rejections"
relay run --loop --backend "$PROVIDER" || true   # iteration cap is OK

# Manual snapshot since cap-reach doesn't auto-snapshot
SNAP=".relay/history/$(date -u +%Y%m%d-%H%M)-bug-rca-fix-tz"
mkdir -p "$SNAP/artifacts"
cp .relay/workflows/default/artifacts/*.md "$SNAP/artifacts/" 2>/dev/null || true
cp .relay/workflows/default/state.yml "$SNAP/state.yml" 2>/dev/null || true
cp .relay/workflows/default/workflow.yml "$SNAP/workflow.yml" 2>/dev/null || true
cp -r .relay/workflows/default/roles "$SNAP/roles" 2>/dev/null || true

# Save run 1's first plan.md so we can diff it later.
cp "$SNAP/artifacts/plan.md" "$OUT/run1-plan.md" 2>/dev/null || true

# --- Distill ---------------------------------------------------------------
echo "==> Distilling lessons"
if [ "$USE_LLM_DISTILL" = "1" ]; then
  relay distill --llm --provider "$PROVIDER" --model "$MODEL"
else
  relay distill
fi

echo "==> Lessons:"
cat .relay/LESSONS.md
echo

# --- Run 2: different bug, same class --------------------------------------
relay reset --clean >/dev/null
cat > .relay/workflows/default/artifacts/context.md <<'EOF'
# Context

Bug: feature-flag value `enable_metrics: "false"` (quoted) is treated
as truthy in `src/myapp/config.py`. We want the same robustness that
the planner produces for any future flag.

- `src/myapp/config.py` calls yaml.safe_load and returns the dict.
- `src/myapp/router.py` reads the flag.
EOF

echo "==> Run 2: bug B (config coercion), same task class — planner now has Run 1's lessons in its prompt"
relay run --loop --backend "$PROVIDER" || true

cp .relay/workflows/default/artifacts/plan.md "$OUT/run2-plan.md" 2>/dev/null || true

# --- Side-by-side diff -----------------------------------------------------
echo
echo "==> Side-by-side: run-1 plan.md vs run-2 plan.md"
echo "    Both are at: $OUT/run{1,2}-plan.md"
echo "    Quick check: how many of the lessons does run-2's plan address from the start?"
echo
echo "Lessons in .relay/LESSONS.md:"
grep -E '^- ' .relay/LESSONS.md || true
echo
echo "Run-2 plan.md (first 80 lines):"
sed -n '1,80p' "$OUT/run2-plan.md"
echo
echo "Done. Compare $OUT/run1-plan.md vs $OUT/run2-plan.md and .relay/LESSONS.md"
