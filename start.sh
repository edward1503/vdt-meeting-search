#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════════════════
#  VDT Meeting Search - Startup Script
#  Hybrid search with Elasticsearch in Docker + self-hosted embeddings in Python
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Usage:  ./start.sh [--skip-index] [--dev] [--index-only]
#
#  Architecture:
#    Docker  → Elasticsearch 8.15 (host port 9201)
#    Host    → FastAPI + sentence-transformers e5-base-v2 in-process
#              (CUDA if available, otherwise CPU; API port 8000)
#
# ═══════════════════════════════════════════════════════════════════════════════

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SKIP_INDEX=false
DEV_MODE=false
INDEX_ONLY=false
ES_HOST="${ES_HOST:-http://localhost:9201}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-intfloat/e5-base-v2}"
EMBEDDING_DIM="${EMBEDDING_DIM:-768}"

for arg in "$@"; do
  case $arg in
    --skip-index) SKIP_INDEX=true ;;
    --dev) DEV_MODE=true ;;
    --index-only) INDEX_ONLY=true ;;
  esac
done

banner() {
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║${NC}  ${BOLD}$1${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

phase() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}  ▶ PHASE $1: $2${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

success() { echo -e "${GREEN}  ✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}  ⚠ $1${NC}"; }
fail()    { echo -e "${RED}  ✗ $1${NC}"; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
banner "VDT Meeting Search — Semantic Search for Meeting Minutes"
# ─────────────────────────────────────────────────────────────────────────────

echo -e "  ${BOLD}Model:${NC}      $EMBEDDING_MODEL (${EMBEDDING_DIM}d, self-hosted)"
echo -e "  ${BOLD}Embedding:${NC}  sentence-transformers in FastAPI/indexing process"
echo -e "  ${BOLD}Backend:${NC}    Elasticsearch 8.15 (Docker)"
echo -e "  ${BOLD}Dataset:${NC}    AMI + QMSum (~170 meetings, ~3000 chunks)"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
phase "1/5" "Prerequisites Check"
# ═══════════════════════════════════════════════════════════════════════════════

command -v python >/dev/null 2>&1 || fail "Python not found"
command -v docker >/dev/null 2>&1 || fail "Docker not found"

PYTHON_VER=$(python --version 2>&1)
success "Python: $PYTHON_VER"

# ═══════════════════════════════════════════════════════════════════════════════
phase "2/5" "Install Dependencies"
# ═══════════════════════════════════════════════════════════════════════════════

if python -c "import sentence_transformers, elasticsearch, fastapi" 2>/dev/null; then
  success "Dependencies already installed"
else
  pip install -r requirements.txt -q
  success "Dependencies installed"
fi

# Check GPU after dependencies are available. Embeddings are self-hosted in the
# same Python process, so this is the device used by indexing and API search.
GPU_STATUS=$(python -c "import torch; print(f'{torch.cuda.get_device_name(0)}' if torch.cuda.is_available() else 'CPU only')" 2>/dev/null || echo "CPU only")
if [[ "$GPU_STATUS" == "CPU only" ]]; then
  warn "Embedding device: CPU only (slower)"
else
  success "Embedding device: $GPU_STATUS"
fi

# ═══════════════════════════════════════════════════════════════════════════════
phase "3/5" "Start Elasticsearch (Docker)"
# ═══════════════════════════════════════════════════════════════════════════════

if curl -s "$ES_HOST" >/dev/null 2>&1; then
  success "Elasticsearch already running at $ES_HOST"
else
  echo "  Starting Elasticsearch container..."
  docker compose -f docker/docker-compose.yml up -d

  echo -n "  Waiting for ES"
  RETRIES=30
  until curl -s "$ES_HOST/_cluster/health" >/dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    [ $RETRIES -le 0 ] && echo "" && fail "Elasticsearch failed to start"
    sleep 2
    echo -n "."
  done
  echo ""
  success "Elasticsearch ready at $ES_HOST"
fi

# ═══════════════════════════════════════════════════════════════════════════════
phase "4/5" "Index Data (Self-host Embedding + Bulk Index)"
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$SKIP_INDEX" = true ]; then
  warn "Skipping indexing (--skip-index)"
else
  DOC_COUNT=$(curl -s "$ES_HOST/meeting_chunks/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")

  if [ "$DOC_COUNT" -gt 2000 ]; then
    success "Index has $DOC_COUNT documents — skipping"
    warn "To re-index: python -m src.indexing.bulk_index --es-host $ES_HOST --recreate"
  else
    echo "  Embedding ~3000 chunks with $EMBEDDING_MODEL on $GPU_STATUS..."
    python -m src.indexing.bulk_index --es-host "$ES_HOST" --recreate
    success "Indexing complete"
  fi
fi

[ "$INDEX_ONLY" = true ] && { echo ""; success "Done (--index-only)"; exit 0; }

# ═══════════════════════════════════════════════════════════════════════════════
phase "5/5" "Start API Server (Host + Self-host Embeddings)"
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}Endpoints:${NC}"
echo -e "    • Search:   ${CYAN}POST http://localhost:8000/search${NC}"
echo -e "    • Swagger:  ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  ${BOLD}Press Ctrl+C to stop${NC}"
echo ""

export ES_HOST EMBEDDING_MODEL EMBEDDING_DIM
if [ "$DEV_MODE" = true ]; then
  warn "Dev mode (--reload)"
  uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
else
  uvicorn src.api.main:app --host 0.0.0.0 --port 8000
fi
