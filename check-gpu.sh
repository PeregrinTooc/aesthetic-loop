#!/usr/bin/env bash
set -euo pipefail

COMFYUI_URL="${COMFYUI_BASE_URL:-http://localhost:8188}"
OK=0
FAIL=0

pass() { echo "  [OK]  $1"; OK=$((OK + 1)); }
fail() { echo "  [!!]  $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "=== ROCm device check ==="

if [ -e /dev/kfd ]; then
    pass "/dev/kfd exists"
else
    fail "/dev/kfd not found — ROCm kernel driver missing or not loaded"
fi

RENDER_DEVS=$(ls /dev/dri/renderD* 2>/dev/null | wc -l)
if [ "$RENDER_DEVS" -gt 0 ]; then
    pass "/dev/dri/renderD* found ($RENDER_DEVS device(s))"
else
    fail "No /dev/dri/renderD* devices found"
fi

if command -v rocm-smi &>/dev/null; then
    if rocm-smi --showid 2>/dev/null | grep -q "GPU"; then
        pass "rocm-smi detects a GPU"
    else
        fail "rocm-smi found but no GPU detected"
    fi
else
    echo "  [--]  rocm-smi not installed, skipping GPU model check"
fi

echo ""
echo "=== ComfyUI reachability ($COMFYUI_URL) ==="

if curl -sf --max-time 5 "$COMFYUI_URL/system_stats" > /dev/null; then
    pass "ComfyUI is reachable at $COMFYUI_URL"
else
    fail "ComfyUI not reachable at $COMFYUI_URL — is it running?"
fi

echo ""
echo "=== workflow.json ==="

if [ -f "workflow.json" ]; then
    if grep -q "%PROMPT%" workflow.json; then
        pass "workflow.json exists and contains %PROMPT% sentinel"
    else
        fail "workflow.json exists but missing %PROMPT% sentinel in positive prompt node"
    fi
else
    fail "workflow.json not found — export from ComfyUI (File → Save [API Format]) and place it here"
fi

echo ""
echo "=== Summary: $OK passed, $FAIL failed ==="
echo ""

[ "$FAIL" -eq 0 ]
