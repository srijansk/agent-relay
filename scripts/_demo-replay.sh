#!/usr/bin/env bash
# Simulated terminal replay used to generate docs/assets/demo.gif.
#
# Pure shell + ANSI escape codes. No relay binary needed, no API key
# needed. The output mirrors what a real `bug-rca-fix` end-to-end run
# produces (drawn from the captured artifacts in docs/demo-output/).
#
# Run via: scripts/generate-demo-gif.sh (do not record interactively).

set -euo pipefail

CYAN=$'\033[36m'
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
RESET=$'\033[0m'

type_out() {
  local text="$1"
  local delay="${2:-0.025}"
  for ((i = 0; i < ${#text}; i++)); do
    printf "%s" "${text:$i:1}"
    sleep "$delay"
  done
  echo
}

prompt() {
  printf "%s\$ %s" "$CYAN" "$RESET"
  type_out "$1"
}

# ---------------------------------------------------------------------------
# Title card
# ---------------------------------------------------------------------------
clear
echo
echo "  ${BOLD}${GREEN}agent-relay${RESET} — multi-agent workflows that learn from past runs"
echo "  ${DIM}github.com/srijansk/agent-relay${RESET}"
echo
sleep 2.5

# ---------------------------------------------------------------------------
# Scene 1 — Run 1 hits the iteration cap (no prior lessons)
# ---------------------------------------------------------------------------
clear
echo "${DIM}# Run 1 — fix a timezone bug. No prior lessons.${RESET}"
echo
prompt "relay init --template bug-rca-fix"
echo "Workflow 'default' initialized at .relay/workflows/default"
echo
sleep 1
prompt "relay run --loop --backend openai"
sleep 0.4
echo "Invoking OpenAI (gpt-4o) for rca_reproducer...   ${GREEN}✓${RESET} repro.md"
sleep 0.6
echo "Invoking OpenAI (gpt-4o) for rca_hypothesizer... ${GREEN}✓${RESET} hypothesis.md"
sleep 0.6
echo "Invoking OpenAI (gpt-4o) for planner...          ${GREEN}✓${RESET} plan.md"
sleep 0.7
echo "Invoking OpenAI (gpt-4o) for reviewer...         ${RED}${BOLD}✗ REQUEST_CHANGES${RESET}"
sleep 1.4
echo "Invoking OpenAI (gpt-4o) for planner...          ${GREEN}✓${RESET} plan.md (revision 2)"
sleep 0.6
echo "Invoking OpenAI (gpt-4o) for reviewer...         ${RED}${BOLD}✗ REQUEST_CHANGES${RESET}"
sleep 1.2
echo
echo "${YELLOW}Warning: Iteration limit reached for 'plan_review': 4/4${RESET}"
sleep 2.5

# ---------------------------------------------------------------------------
# Scene 2 — relay distill --llm compresses the rejections
# ---------------------------------------------------------------------------
clear
echo "${DIM}# Compile typed lessons from Run 1's rejections.${RESET}"
echo
prompt "relay distill --llm"
sleep 0.4
echo "Distilling with LLM (openai / gpt-4o)..."
sleep 0.9
echo "${GREEN}Distilled 5 lesson(s) from 1 run(s) (llm).${RESET}"
sleep 1
prompt "cat .relay/LESSONS.md"
sleep 0.4
echo
echo "${BOLD}## Planner (5)${RESET}"
echo
sleep 0.4
echo "- ${YELLOW}[warn]${RESET} Always include a specific failing test that demonstrates"
echo "        the bug before applying any fixes."
sleep 1.4
echo "- ${YELLOW}[warn]${RESET} Always specify the exact file changes or commits to"
echo "        undo in the rollback section."
sleep 1.4
echo "- ${YELLOW}[warn]${RESET} Explicitly review and test adjacent code paths for"
echo "        similar issues when addressing a bug."
sleep 2.5

# ---------------------------------------------------------------------------
# Scene 3 — Run 2: different bug, same task class, lessons in prompt
# ---------------------------------------------------------------------------
clear
echo "${DIM}# Run 2 — different bug, same task class. Lessons auto-injected.${RESET}"
echo
prompt "relay reset --clean && relay run --loop --backend openai"
sleep 0.6
echo "Invoking OpenAI (gpt-4o) for rca_reproducer...   ${GREEN}✓${RESET} repro.md"
sleep 0.5
echo "Invoking OpenAI (gpt-4o) for rca_hypothesizer... ${GREEN}✓${RESET} hypothesis.md"
sleep 0.5
echo "Invoking OpenAI (gpt-4o) for planner...          ${GREEN}✓${RESET} plan.md"
sleep 0.8
echo "Invoking OpenAI (gpt-4o) for reviewer...         ${GREEN}${BOLD}✓ APPROVE${RESET} ${DIM}(first pass)${RESET}"
sleep 1.6
echo "Invoking OpenAI (gpt-4o) for implementer...      ${GREEN}✓${RESET} build_log.md"
sleep 0.5
echo "Invoking OpenAI (gpt-4o) for auditor...          ${GREEN}✓${RESET} APPROVE"
sleep 0.6
echo
echo "${GREEN}Workflow complete!${RESET}"
echo "${DIM}Snapshotted run to .relay/history/<run-id>${RESET}"
sleep 1.5

# ---------------------------------------------------------------------------
# Closing card
# ---------------------------------------------------------------------------
echo
echo "  ${BOLD}${GREEN}► Run 2 approved on first pass — lessons compounded.${RESET}"
echo "  ${DIM}docs/demo-output/ has the full captured run.${RESET}"
echo
sleep 3
