#!/usr/bin/env bash
# Generate docs/assets/demo.gif fully programmatically.
#
# Records scripts/_demo-replay.sh inside an asciinema session, then
# converts the resulting cast to a GIF with `agg`. No API key, no live
# LLM calls, no manual recording — one command in, one GIF out.
#
# Usage:
#   ./scripts/generate-demo-gif.sh
#
# Tools required (one-time install):
#   brew install asciinema agg
#
# Output:
#   docs/assets/demo.gif    — the hero gif referenced by the README
#   docs/assets/demo.cast   — the raw asciicast (kept so you can
#                              re-render the gif at different sizes
#                              without re-running the replay)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$REPO/docs/assets"
REPLAY="$REPO/scripts/_demo-replay.sh"
CAST="$ASSETS/demo.cast"
GIF="$ASSETS/demo.gif"

# --- preflight ---------------------------------------------------------------
for tool in asciinema agg; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "✗ missing tool: $tool"
    echo "  install with: brew install asciinema agg"
    exit 1
  fi
done

if [ ! -x "$REPLAY" ]; then
  echo "Making $REPLAY executable…"
  chmod +x "$REPLAY"
fi

mkdir -p "$ASSETS"

# --- record ------------------------------------------------------------------
echo "→ Recording replay (≈45s)…"
rm -f "$CAST"
asciinema rec "$CAST" \
  --command "$REPLAY" \
  --idle-time-limit 1.5 \
  --cols 100 \
  --rows 28 \
  --quiet

# --- convert -----------------------------------------------------------------
echo "→ Rendering GIF with agg…"
rm -f "$GIF"
agg --font-size 14 --theme monokai --speed 1.0 "$CAST" "$GIF"

# --- summary -----------------------------------------------------------------
GIF_SIZE_KB=$(du -k "$GIF" | cut -f1)
echo
echo "✓ Generated:"
echo "    $GIF  (${GIF_SIZE_KB} KB)"
echo "    $CAST"
echo
echo "Commit it:"
echo "    git add docs/assets/demo.gif docs/assets/demo.cast"
echo "    git commit -m 'docs: add hero demo gif'"
echo "    git push origin v0.2-lessons"
