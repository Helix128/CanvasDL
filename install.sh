#!/usr/bin/env bash
# Install CanvasDL and register its MCP server for Claude Code, Codex and Antigravity.
# Safe to re-run: existing "canvasdl" entries are updated.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
cd "$DIR"

[ -x "$PY" ] || python3 -m venv .venv
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/canvasdl"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR" 2>/dev/null || true

TOKEN_FILE="$CONFIG_DIR/canvas_token.txt"
if [ ! -s "$TOKEN_FILE" ] && [ -s "$DIR/canvas_token.txt" ]; then
  cp "$DIR/canvas_token.txt" "$TOKEN_FILE"
fi

if [ ! -s "$TOKEN_FILE" ]; then
  read -rsp "Canvas access token (Canvas > Cuenta > Configuraciones > Nuevo token de acceso): " token; echo
  printf '%s' "$token" > "$TOKEN_FILE"
fi
chmod 600 "$TOKEN_FILE" 2>/dev/null || true
[ -f "$DIR/canvas_token.txt" ] && chmod 600 "$DIR/canvas_token.txt" 2>/dev/null || true

PYTHONPATH="$DIR" "$PY" -c "from app.canvas_api import canvas_client as c; a=c.verify_auth(); print('✓ Canvas autenticado:', a['user']['name'] if a['authenticated'] else a['error'])"

# Register in Claude Code
if command -v claude >/dev/null; then
  claude mcp remove -s user canvasdl >/dev/null 2>&1 || true
  claude mcp add -s user canvasdl -e PYTHONPATH="$DIR" -- "$PY" -m app.mcp_server
  echo "✓ Claude Code: canvasdl registrado exitosamente."
else
  echo "• Claude Code no encontrado en PATH (omitiendo registro automático)."
fi

# Register in Codex
if command -v codex >/dev/null; then
  codex mcp remove canvasdl >/dev/null 2>&1 || true
  codex mcp add canvasdl --env PYTHONPATH="$DIR" -- "$PY" -m app.mcp_server
  echo "✓ Codex: canvasdl registrado exitosamente."
else
  echo "• Codex no encontrado en PATH (omitiendo registro automático)."
fi

# Register in Antigravity
if [ -d "$HOME/.gemini" ]; then
  "$PY" - "$HOME/.gemini/config/mcp_config.json" "$DIR" <<'EOF'
import json, sys
from pathlib import Path
path, root = Path(sys.argv[1]), sys.argv[2]
data = json.loads(path.read_text()) if path.exists() else {}
data.setdefault("mcpServers", {})["canvasdl"] = {
    "command": f"{root}/.venv/bin/python", "args": ["-m", "app.mcp_server"], "env": {"PYTHONPATH": root}}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"✓ Antigravity: canvasdl registrado en {path}")
EOF
else
  echo "• Antigravity: ~/.gemini no encontrado (omitiendo)."
fi

echo ""
echo "=== Instalación completa ==="
echo "1. Para Claude Code: Ya está listo. Reinicia claude code."
echo "2. Para Claude Web (claude.ai): Consulta la sección 'Claude Web' en README.md."
