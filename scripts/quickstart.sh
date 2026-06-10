#!/usr/bin/env bash
# scripts/quickstart.sh
# One-command setup: validates prerequisites, pulls model, and starts all services.
# Usage: ./scripts/quickstart.sh [--dev] [--model aya-expanse:8b]

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

COMPOSE_FILE="docker-compose.yml"
MODEL="aya-expanse:32b"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --dev)    COMPOSE_FILE="docker-compose.yml -f docker-compose.override.yml"; shift ;;
    --model)  MODEL="$2"; shift 2 ;;
    --small)  MODEL="aya-expanse:8b"; shift ;;
    *) error "Unknown argument: $1" ;;
  esac
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   🤖 HR Assistant — Quick Start Setup    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# --- Prerequisites ---
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker not found. Install Docker Desktop or Docker Engine."
command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1 || error "docker-compose not found."

DOCKER_COMPOSE="docker-compose"
docker compose version >/dev/null 2>&1 && DOCKER_COMPOSE="docker compose"

info "Docker: $(docker --version)"
info "Using model: $MODEL"

# --- Check VRAM ---
if command -v nvidia-smi >/dev/null 2>&1; then
  VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
  info "GPU VRAM: ${VRAM} MiB"
  if [[ "$MODEL" == "aya-expanse:32b" && "$VRAM" -lt 22000 ]]; then
    warn "Less than 22 GB VRAM detected. Switching to aya-expanse:8b automatically."
    MODEL="aya-expanse:8b"
  fi
else
  warn "No NVIDIA GPU detected. Running on CPU (very slow). Consider --small flag."
fi

# --- Environment ---
if [[ ! -f .env ]]; then
  info "Creating .env from .env.example..."
  cp .env.example .env
  # Generate a random JWT secret
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
  sed -i.bak "s/CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_BASE64_32/${JWT_SECRET}/" .env
  rm -f .env.bak
  info ".env created with random JWT secret."
fi

# Set model in .env
sed -i.bak "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=${MODEL}|" .env 2>/dev/null || true
rm -f .env.bak

# --- Pull images ---
info "Pulling Docker images (this may take a few minutes on first run)..."
$DOCKER_COMPOSE -f $COMPOSE_FILE pull --quiet 2>/dev/null || true

# --- Start services ---
info "Starting all services..."
$DOCKER_COMPOSE -f $COMPOSE_FILE up -d

# --- Wait for health ---
info "Waiting for services to be ready..."

wait_for() {
  local name=$1 url=$2 max=$3
  local count=0
  while ! curl -sf "$url" >/dev/null 2>&1; do
    count=$((count + 1))
    if [[ $count -gt $max ]]; then
      error "$name did not become healthy after $((max * 5))s. Check: $DOCKER_COMPOSE logs $name"
    fi
    printf "  Waiting for %-20s (%ds)...\r" "$name" $((count * 5))
    sleep 5
  done
  info "$name is ready ✓"
}

wait_for "postgres"   "http://localhost:5432" 12
wait_for "chromadb"   "http://localhost:8002/api/v1/heartbeat" 12
wait_for "ollama"     "http://localhost:11434/api/tags" 24
wait_for "backend"    "http://localhost:8000/health" 24
wait_for "frontend"   "http://localhost:80" 12

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅ HR Assistant is ready!                   ║"
echo "║                                              ║"
echo "║  🌐 Open: http://localhost                   ║"
echo "║                                              ║"
echo "║  Demo accounts (password: demo1234):         ║"
echo "║    ahmed@company.sa    — Software Engineer   ║"
echo "║    sara@company.sa     — HR Manager          ║"
echo "║    khalid@company.sa   — Data Analyst        ║"
echo "║    mona@company.sa     — DevOps Lead         ║"
echo "║                                              ║"
echo "║  API Docs: http://localhost/api/docs         ║"
echo "║  Logs:  docker-compose logs -f               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
