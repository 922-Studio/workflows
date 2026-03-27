#!/usr/bin/env bash
# pr-demo.sh — Generic Docker-based PR preview environment manager
#
# Usage:
#   pr-demo.sh start <pr-number> <branch>   — spin up a preview container stack
#   pr-demo.sh stop  <pr-number>            — tear down preview and clean up
#   pr-demo.sh list                         — show all running previews with URLs
#   pr-demo.sh status                       — machine-readable JSON status
#
# Configuration (via environment variables):
#   PROJECT_NAME        (required) — e.g. "drafter"
#   REPO_PATH           (required) — absolute path to repo on server, e.g. "/home/lab/Drafter"
#   PORT_BASE           (optional, default: 9100) — preview port = PORT_BASE + (PR_NUMBER % PORT_RANGE)
#   PORT_RANGE          (optional, default: 100)  — port range before wrapping (PR 100 reuses port of PR 0)
#   MAX_DEMOS           (optional, default: 5)    — max concurrent previews allowed
#   COMPOSE_FILE        (optional, default: "docker-compose.yaml") — compose file to use
#   PREVIEW_DOMAIN      (optional) — domain pattern for public preview, e.g. "922-studio.com"
#                         When set, generates URL: {PROJECT_NAME}-pr-{N}.{PREVIEW_DOMAIN}
#                         When unset, falls back to http://{TAILSCALE_IP}:{port}
#   TAILSCALE_IP        (optional, default: "100.112.171.16") — fallback IP when PREVIEW_DOMAIN is not set
#   HEALTHCHECK_PATH    (optional, default: "/api/health") — path to verify container is up
#   HEALTHCHECK_TIMEOUT (optional, default: 60) — seconds to wait for healthy container
#   CONTAINER_PORT      (optional, default: 3000) — internal container port to map to the preview port
#
# State is tracked via /tmp/{PROJECT_NAME}-pr-state/ (one JSON file per PR).
# Git worktrees live at /tmp/{PROJECT_NAME}-pr/pr-{number}.
#
# Designed to be called by the reusable pr-demo.yml GitHub Actions workflow.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

: "${PROJECT_NAME:?PROJECT_NAME is required (e.g. drafter)}"
: "${REPO_PATH:?REPO_PATH is required (e.g. /home/lab/Drafter)}"

PORT_BASE="${PORT_BASE:-9100}"
PORT_RANGE="${PORT_RANGE:-100}"
MAX_DEMOS="${MAX_DEMOS:-5}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"
PREVIEW_DOMAIN="${PREVIEW_DOMAIN:-}"
TAILSCALE_IP="${TAILSCALE_IP:-100.112.171.16}"
HEALTHCHECK_PATH="${HEALTHCHECK_PATH:-/api/health}"
HEALTHCHECK_TIMEOUT="${HEALTHCHECK_TIMEOUT:-60}"
CONTAINER_PORT="${CONTAINER_PORT:-3000}"

WORKTREE_BASE="/tmp/${PROJECT_NAME}-pr"
STATE_DIR="/tmp/${PROJECT_NAME}-pr-state"

# ── Colors & Logging ──────────────────────────────────────────────────────────

RED='\033[0;31m'; GRN='\033[0;32m'; CYN='\033[0;36m'; YLW='\033[0;33m'
BLD='\033[1m'; RST='\033[0m'

log()  { echo -e "${CYN}▶${RST} $*"; }
ok()   { echo -e "${GRN}✓${RST} $*"; }
warn() { echo -e "${YLW}⚠${RST} $*"; }
die()  { echo -e "${RED}✗${RST} $*" >&2; exit 1; }

# ── Helpers ───────────────────────────────────────────────────────────────────

# Compute the preview port for a given PR number (wraps at PORT_RANGE)
preview_port() { echo $(( PORT_BASE + ($1 % PORT_RANGE) )); }

# Build the public preview URL for a given PR number
preview_url() {
  local pr=$1 port=$2
  if [[ -n "$PREVIEW_DOMAIN" ]]; then
    echo "https://${PROJECT_NAME}-pr-${pr}.${PREVIEW_DOMAIN}"
  else
    echo "http://${TAILSCALE_IP}:${port}"
  fi
}

# Build the public hostname for Traefik routing
preview_hostname() {
  local pr=$1
  echo "${PROJECT_NAME}-pr-${pr}.${PREVIEW_DOMAIN}"
}

# Check if a port is available (not bound by another process)
check_port_available() {
  local port=$1 pr=$2
  # Check if any OTHER PR demo is using this port (port collision from wrapping)
  for f in "${STATE_DIR}"/pr-*.json; do
    [[ -f "$f" ]] || continue
    local existing_pr; existing_pr=$(basename "$f" | sed 's/pr-\([0-9]*\)\.json/\1/')
    [[ "$existing_pr" == "$pr" ]] && continue  # skip self
    local existing_port
    existing_port=$(grep -o '"port": *[0-9]*' "$f" 2>/dev/null | grep -o '[0-9]*$' || echo "0")
    if [[ "$existing_port" == "$port" ]]; then
      local proj; proj=$(compose_proj "$existing_pr")
      if docker compose -p "$proj" ps -q 2>/dev/null | grep -q .; then
        die "PORT_CONFLICT: Port ${port} is already in use by PR #${existing_pr} (port wrapping collision). Stop PR #${existing_pr} first."
      else
        # Stale state — clean it up
        warn "Cleaning up stale state for PR #${existing_pr} on port ${port}"
        cleanup_demo "$existing_pr"
      fi
    fi
  done
  # Also check if port is bound by a non-demo process
  if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    die "PORT_IN_USE: Port ${port} is already bound by another process on this server."
  fi
}

# Path helpers
state_file()   { echo "${STATE_DIR}/pr-${1}.json"; }
worktree_dir() { echo "${WORKTREE_BASE}/pr-${1}"; }
compose_proj() { echo "${PROJECT_NAME}-pr-${1}"; }

# Count how many previews are currently running (have a state file with a live compose project)
count_running() {
  local count=0
  for f in "${STATE_DIR}"/pr-*.json; do
    [[ -f "$f" ]] || continue
    local pr; pr=$(basename "$f" | sed 's/pr-\([0-9]*\)\.json/\1/')
    local proj; proj=$(compose_proj "$pr")
    # Check if compose project has any running containers
    if docker compose -p "$proj" ps -q 2>/dev/null | grep -q .; then
      ((count++)) || true
    fi
  done
  echo "$count"
}

# Write metadata to the state file for a given PR
write_state() {
  local pr=$1 branch=$2 port=$3
  local url; url=$(preview_url "$pr" "$port")
  mkdir -p "$STATE_DIR"
  cat > "$(state_file "$pr")" <<EOF
{
  "pr": $pr,
  "branch": "$branch",
  "port": $port,
  "project": "$(compose_proj "$pr")",
  "url": "$url",
  "started_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
}

# Read a field from the state file (uses grep + sed to avoid jq dependency)
read_state_field() {
  local file=$1 field=$2
  grep -o "\"${field}\": *\"[^\"]*\"" "$file" 2>/dev/null \
    | sed 's/.*": *"\(.*\)"/\1/' || echo ""
}

# Stop and remove a running compose project, then clean up worktree and state
cleanup_demo() {
  local pr=$1
  local proj; proj=$(compose_proj "$pr")
  local worktree; worktree=$(worktree_dir "$pr")
  local sf; sf=$(state_file "$pr")

  log "Stopping compose project: $proj"
  # --rmi local removes only images built by compose (not pulled base images)
  docker compose -p "$proj" down --rmi local -v 2>/dev/null || true
  ok "Containers stopped and removed"

  # Remove git worktree
  if [[ -d "$worktree" ]]; then
    log "Removing git worktree: $worktree"
    git -C "$REPO_PATH" worktree remove --force "$worktree" 2>/dev/null || true
    rm -rf "$worktree"
    ok "Worktree removed"
  fi

  # Remove state file
  rm -f "$sf"
}

# Wait for the healthcheck endpoint to respond, up to HEALTHCHECK_TIMEOUT seconds
wait_for_health() {
  local port=$1 pr=$2
  local url
  if [[ -n "$PREVIEW_DOMAIN" ]]; then
    # Traefik-routed: hit localhost with Host header so Traefik can route it
    local hostname; hostname=$(preview_hostname "$pr")
    url="http://localhost${HEALTHCHECK_PATH}"
    log "Waiting for health via Traefik (Host: ${hostname}, timeout: ${HEALTHCHECK_TIMEOUT}s)"
    local deadline=$(( $(date +%s) + HEALTHCHECK_TIMEOUT ))
    while [[ $(date +%s) -lt $deadline ]]; do
      local code
      code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${hostname}" "$url" 2>/dev/null || echo "000")
      if [[ "$code" =~ ^[2-3][0-9]{2}$ ]]; then
        ok "Container healthy (HTTP $code)"
        return 0
      fi
      sleep 2
    done
  else
    url="http://localhost:${port}${HEALTHCHECK_PATH}"
    log "Waiting for health at ${url} (timeout: ${HEALTHCHECK_TIMEOUT}s)"
    local deadline=$(( $(date +%s) + HEALTHCHECK_TIMEOUT ))
    while [[ $(date +%s) -lt $deadline ]]; do
      local code
      code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
      if [[ "$code" =~ ^[2-3][0-9]{2}$ ]]; then
        ok "Container healthy (HTTP $code)"
        return 0
      fi
      sleep 2
    done
  fi

  warn "Container did not respond within ${HEALTHCHECK_TIMEOUT}s (last code: ${code:-000})"
  return 1
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_start() {
  local pr=$1 branch=$2
  local port; port=$(preview_port "$pr")
  local worktree; worktree=$(worktree_dir "$pr")
  local proj; proj=$(compose_proj "$pr")
  local sf; sf=$(state_file "$pr")

  log "Starting PR #${pr} preview (branch: ${branch}, port: ${port})"

  # ── 1. Check capacity ──────────────────────────────────────────────────────
  local running; running=$(count_running)
  if [[ "$running" -ge "$MAX_DEMOS" ]]; then
    die "AT_CAPACITY: ${running}/${MAX_DEMOS} previews running. Stop one before starting another."
  fi
  log "Capacity: ${running}/${MAX_DEMOS} slots in use"

  # ── 2. Clean up stale demo if exists ──────────────────────────────────────
  if [[ -f "$sf" ]] || docker compose -p "$proj" ps -q 2>/dev/null | grep -q .; then
    warn "Stale demo detected for PR #${pr} — cleaning up first"
    cleanup_demo "$pr"
  fi

  # ── 2b. Check port availability (handles wrapping collisions) ────────────
  check_port_available "$port" "$pr"

  # ── 3. Create git worktree from PR branch ─────────────────────────────────
  log "Fetching latest refs from origin..."
  git -C "$REPO_PATH" fetch --quiet origin 2>/dev/null || warn "Fetch failed — using local refs"

  # Resolve branch reference (prefers remote tracking branch)
  local full_ref=""
  if git -C "$REPO_PATH" show-ref --verify --quiet "refs/remotes/origin/${branch}" 2>/dev/null; then
    full_ref="origin/${branch}"
  elif git -C "$REPO_PATH" show-ref --verify --quiet "refs/heads/${branch}" 2>/dev/null; then
    full_ref="$branch"
  else
    die "Branch not found locally or on origin: ${branch}"
  fi

  mkdir -p "$WORKTREE_BASE"

  # Clean up leftover worktree from a previous failed run
  if [[ -d "$worktree" ]]; then
    warn "Leftover worktree found at ${worktree} — removing"
    git -C "$REPO_PATH" worktree remove --force "$worktree" 2>/dev/null || true
    rm -rf "$worktree"
  fi

  # Prune stale worktree entries (registered but directory missing)
  git -C "$REPO_PATH" worktree prune

  log "Creating worktree at: ${worktree}"
  git -C "$REPO_PATH" worktree add --detach "$worktree" "$full_ref"
  ok "Worktree created from ${full_ref}"

  # ── 4. Prepare .env for the preview container ──────────────────────────────
  # Copy .env from main repo if it exists, then overlay PR-specific overrides.
  # Traefik routing is disabled for demos; each preview gets a unique port.
  if [[ -f "${REPO_PATH}/.env" ]]; then
    log "Copying .env from main repo..."
    cp "${REPO_PATH}/.env" "${worktree}/.env"
  else
    log "No .env in main repo — creating fresh one"
    touch "${worktree}/.env"
  fi

  # Override / append PR-specific variables.
  # We remove any existing definitions first to avoid duplicates, then append.
  local env_file="${worktree}/.env"

  # Remove existing keys that we will override
  for key in APP_PORT CONTAINER_NAME ROUTER_NAME TRAEFIK_HOST \
              TRAEFIK_ENABLE traefik.enable; do
    sed -i "/^${key}=/d" "$env_file" 2>/dev/null || true
  done

  # Append PR-specific overrides
  if [[ -n "$PREVIEW_DOMAIN" ]]; then
    local hostname; hostname=$(preview_hostname "$pr")
    cat >> "$env_file" <<EOF

# ── PR Preview Overrides (auto-generated by pr-demo.sh) ──────────────────────
APP_PORT=${port}
CONTAINER_NAME=${PROJECT_NAME}_pr_${pr}
ROUTER_NAME=${PROJECT_NAME}-pr-${pr}
# Traefik enabled — public subdomain routing via ${hostname}
TRAEFIK_ENABLE=true
TRAEFIK_HOST=${hostname}
EOF
  else
    cat >> "$env_file" <<EOF

# ── PR Preview Overrides (auto-generated by pr-demo.sh) ──────────────────────
APP_PORT=${port}
CONTAINER_NAME=${PROJECT_NAME}_pr_${pr}
ROUTER_NAME=${PROJECT_NAME}-pr-${pr}
# Traefik disabled for preview containers — access directly via port
TRAEFIK_ENABLE=false
TRAEFIK_HOST=pr-${pr}.preview.local
EOF
  fi

  ok ".env prepared for PR #${pr}"

  # ── 4b. Create compose override for port mapping ───────────────────────────
  # The project compose file may not expose ports (relying on Traefik). For
  # previews we need a host port mapping so the container is directly accessible.
  # Discover the first service name and generate an override file in the worktree.
  local first_service
  first_service=$(docker compose -f "${worktree}/${COMPOSE_FILE}" --project-directory "$worktree" config --services 2>/dev/null | head -1)

  if [[ -n "$first_service" ]]; then
    local override_file="${worktree}/docker-compose.preview.yml"
    cat > "$override_file" <<EOF
services:
  ${first_service}:
    ports:
      - "${port}:${CONTAINER_PORT}"
EOF
    ok "Compose override created: port ${port} → 3000 (service: ${first_service})"
  else
    warn "Could not detect service name — skipping port override"
  fi

  # ── 5. Build and start with docker compose ─────────────────────────────────
  log "Building and starting containers (project: ${proj})..."
  log "This may take a while for the first build..."

  local compose_args=(-p "$proj" -f "${worktree}/${COMPOSE_FILE}")
  if [[ -f "${worktree}/docker-compose.preview.yml" ]]; then
    compose_args+=(-f "${worktree}/docker-compose.preview.yml")
  fi

  docker compose \
    "${compose_args[@]}" \
    --project-directory "$worktree" \
    up -d --build --wait --wait-timeout "$HEALTHCHECK_TIMEOUT"

  ok "Containers started"

  # ── 6. Verify healthcheck and report URL ──────────────────────────────────
  local url; url=$(preview_url "$pr" "$port")
  if wait_for_health "$port" "$pr"; then
    write_state "$pr" "$branch" "$port"
    ok "Preview live for PR #${pr}"
    echo ""
    echo "STARTED pr=${pr} url=${url} branch=${branch}"
  else
    # Containers are up but health endpoint not responding — still report URL
    # with a warning so the workflow comment can surface it
    write_state "$pr" "$branch" "$port"
    warn "Preview started but health endpoint did not respond — container may still be initialising"
    echo ""
    echo "STARTED pr=${pr} url=${url} branch=${branch} health=unknown"
  fi
}

cmd_stop() {
  local pr=$1
  local sf; sf=$(state_file "$pr")
  local proj; proj=$(compose_proj "$pr")

  # Guard: nothing to stop
  if [[ ! -f "$sf" ]] && ! docker compose -p "$proj" ps -q 2>/dev/null | grep -q .; then
    warn "No active demo found for PR #${pr}"
    exit 0
  fi

  log "Stopping preview for PR #${pr}..."
  cleanup_demo "$pr"
  ok "PR #${pr} preview stopped and cleaned up"
  echo ""
  echo "STOPPED pr=${pr}"
}

cmd_list() {
  mkdir -p "$STATE_DIR"
  echo -e "${BLD}Running PR Previews — ${PROJECT_NAME}${RST}"
  echo -e "────────────────────────────────────────────────"

  local found=0
  for f in "${STATE_DIR}"/pr-*.json; do
    [[ -f "$f" ]] || continue
    local pr; pr=$(basename "$f" | sed 's/pr-\([0-9]*\)\.json/\1/')
    local proj; proj=$(compose_proj "$pr")
    local url branch started_at

    url=$(read_state_field "$f" "url")
    branch=$(read_state_field "$f" "branch")
    started_at=$(read_state_field "$f" "started_at")

    # Check if compose project is actually running
    if docker compose -p "$proj" ps -q 2>/dev/null | grep -q .; then
      echo -e "  ${GRN}●${RST} PR #${pr}  →  ${BLD}${url}${RST}"
      echo -e "      Branch:  ${branch}"
      echo -e "      Started: ${started_at}"
      ((found++)) || true
    else
      echo -e "  ${RED}●${RST} PR #${pr}  (stale state — run: pr-demo.sh stop ${pr})"
    fi
  done

  [[ "$found" -eq 0 ]] && echo "  No active previews"
  echo -e "────────────────────────────────────────────────"
  echo -e "  ${found}/${MAX_DEMOS} slots used"
}

cmd_status() {
  mkdir -p "$STATE_DIR"
  local demos=()
  local running=0

  for f in "${STATE_DIR}"/pr-*.json; do
    [[ -f "$f" ]] || continue
    local pr; pr=$(basename "$f" | sed 's/pr-\([0-9]*\)\.json/\1/')
    local proj; proj=$(compose_proj "$pr")

    local url branch port started_at
    url=$(read_state_field "$f" "url")
    branch=$(read_state_field "$f" "branch")
    port=$(read_state_field "$f" "port")
    started_at=$(read_state_field "$f" "started_at")

    if docker compose -p "$proj" ps -q 2>/dev/null | grep -q .; then
      demos+=("{\"pr\":${pr},\"port\":${port},\"url\":\"${url}\",\"branch\":\"${branch}\",\"started_at\":\"${started_at}\",\"status\":\"running\"}")
      ((running++)) || true
    fi
  done

  # Build JSON array manually (avoids jq dependency)
  local demos_json
  if [[ ${#demos[@]} -eq 0 ]]; then
    demos_json="[]"
  else
    demos_json=$(printf '%s,' "${demos[@]}")
    demos_json="[${demos_json%,}]"
  fi

  local at_capacity="false"
  [[ "$running" -ge "$MAX_DEMOS" ]] && at_capacity="true"

  echo "{\"project\":\"${PROJECT_NAME}\",\"running\":${running},\"max\":${MAX_DEMOS},\"at_capacity\":${at_capacity},\"demos\":${demos_json}}"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

CMD="${1:-}"
case "$CMD" in
  start)
    [[ $# -ge 3 ]] || die "Usage: pr-demo.sh start <pr-number> <branch>"
    cmd_start "$2" "$3"
    ;;
  stop)
    [[ $# -ge 2 ]] || die "Usage: pr-demo.sh stop <pr-number>"
    cmd_stop "$2"
    ;;
  list)
    cmd_list
    ;;
  status)
    cmd_status
    ;;
  *)
    die "Usage: pr-demo.sh <start|stop|list|status>"
    ;;
esac
