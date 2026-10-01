#!/bin/bash
# KeenRoudy Sports research desk: the only thing launchd calls.
# Separate from MGL by design: nothing here reads ~/.mgl, ~/.config/mgl or ~/Library/Logs/MGL.
#
#   run.sh doctor            print versions, identities and which env keys are set (no values)
#   run.sh py SCRIPT [args]  run a repo script with the sports environment, printing to the terminal
#   run.sh [run.py args]     run scripts/run.py in the repo with the sports environment
#   run.sh precheck          the last look before a scheduled post (launchd, every 30 minutes)
#   run.sh mirror            mirror a Buffer-confirmed X post to Discord (launchd, every 5 minutes)
set -euo pipefail

export HOME=/Users/keen
export TZ=America/New_York
export LANG=en_US.UTF-8
export PYTHONUNBUFFERED=1
export GIT_CONFIG_NOSYSTEM=1
export PATH=/opt/homebrew/bin:/Users/keen/.nvm/versions/node/v22.16.0/bin:/usr/bin:/bin:/usr/sbin:/sbin
export GH_CONFIG_DIR=/Users/keen/.config/keenroudy/gh

CONF=/Users/keen/.config/keenroudy
LOGS=/Users/keen/Library/Logs/KeenRoudy
mkdir -p "$LOGS"

# Load KEY=value lines one by one instead of sourcing the file, so a stray space or a value that
# looks like a command can never be executed. Comments and blank lines are skipped; inline comments
# and surrounding quotes are stripped.
if [ -f "$CONF/env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"; value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%%#*}"
    value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")"
    case "$key" in [A-Za-z_]*) export "$key=$value" ;; esac
  done < "$CONF/env"
fi
: "${KEENROUDY_REPO:=/Users/keen/Projects/sports}"
export KEENROUDY_REPO

doctor() {
  echo "date            $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "localtime       $(readlink /etc/localtime | sed 's|.*/zoneinfo/||')"
  echo "python3         $(python3 --version 2>&1)  ($(command -v python3))"
  echo "node            $(node --version 2>&1)"
  echo "git             $(git --version)"
  echo "repo            $KEENROUDY_REPO"
  echo "git identity    $(git -C "$KEENROUDY_REPO" config user.name) <$(git -C "$KEENROUDY_REPO" config user.email)>"
  echo "git remote      $(git -C "$KEENROUDY_REPO" remote get-url origin)"
  echo "git clean       $(if [ -z "$(git -C "$KEENROUDY_REPO" status --porcelain)" ]; then echo yes; else echo NO; fi)"
  echo "gh account      $(gh auth status 2>&1 | grep -oE 'account [^ ]+' | head -1 || echo 'not logged in')  (GH_CONFIG_DIR=$GH_CONFIG_DIR)"
  echo "ollama          $(curl -s -m 3 http://localhost:11434/api/version 2>/dev/null || echo 'not reachable')"
  echo "codex           $(codex --version 2>/dev/null || echo 'not found')  (codex login status: $(codex login status 2>&1 | head -1 || echo 'unknown'))"
  local keys=""
  for k in ODDS_API_KEY SHARP_API X_API_KEY X_API_SECRET X_ACCESS_TOKEN X_ACCESS_SECRET KEENROUDY_LLM_MODEL KEENROUDY_LLM_FAST_MODEL KEENROUDY_LLM_POLISH KEENROUDY_RESEARCHER KEENROUDY_RESEARCHER_MODEL KEENROUDY_RESEARCHER_REASONING KEENROUDY_REVIEW_MODEL KEENROUDY_REVIEW_REASONING KEENROUDY_X_AUTONOMOUS BUFFER_TOKEN BUFFER_CHANNEL DISCORD_WEBHOOK_URL DISCORD_ARB_WEBHOOK_URL KEENROUDY_NTFY_TOPIC; do
    if [ -n "${!k:-}" ]; then keys="$keys $k"; fi
  done
  echo "env keys set   ${keys:- (none)}"
}

if [ "${1:-}" = "doctor" ] || [ "${1:-}" = "--version" ]; then
  doctor
  exit 0
fi

# run.sh py scripts/buffer_post.py channels   -> a repo script with the sports environment, output to the terminal
if [ "${1:-}" = "py" ]; then
  shift
  cd "$KEENROUDY_REPO"
  exec python3 "$@"
fi

exec >> "$LOGS/run-$(date +%Y-%m-%d).log" 2>&1
find "$LOGS" -name 'run-*.log' -mtime +30 -delete 2>/dev/null || true
# The half-hourly pre-post check and five-minute Discord mirror speak only when work is due.
if [ "${1:-}" != "precheck" ] && [ "${1:-}" != "mirror" ]; then echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') run.sh $*"; fi
cd "$KEENROUDY_REPO"
exec python3 scripts/run.py "$@"
