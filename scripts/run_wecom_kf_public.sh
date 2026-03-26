#!/usr/bin/env bash

set -euo pipefail

PORT="${PORT:-8010}"
HOST="${HOST:-127.0.0.1}"
CALLBACK_PATH="${CALLBACK_PATH:-/wecom/kf/callback}"
WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="${TMP_DIR:-/tmp/agent_kf_wecom}"
SERVER_LOG="${TMP_DIR}/wecom-server.log"
TUNNEL_LOG="${TMP_DIR}/wecom-tunnel.log"
LOCAL_CLOUDFLARED="${WORKDIR}/tools/cloudflared"
PUBLIC_BASE_URL=""

mkdir -p "${TMP_DIR}"

SERVER_PID=""
TUNNEL_PID=""

cleanup() {
  if [[ -n "${TUNNEL_PID}" ]] && kill -0 "${TUNNEL_PID}" 2>/dev/null; then
    kill "${TUNNEL_PID}" 2>/dev/null || true
  fi
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

print_usage() {
  cat <<EOF
用法:
  ./scripts/run_wecom_kf_public.sh

可选环境变量:
  PORT=8010
  HOST=127.0.0.1
  CALLBACK_PATH=/wecom/kf/callback

说明:
  1. 启动企业微信客服测试服务
  2. 自动尝试用 cloudflared 或 ngrok 暴露公网地址
  3. 打印企业微信后台应填写的回调 URL
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1" >&2
    exit 1
  fi
}

wait_for_health() {
  local url="http://${HOST}:${PORT}/health"
  local i
  for i in {1..30}; do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "本地服务健康检查失败: ${url}" >&2
  echo "服务日志:" >&2
  tail -n 50 "${SERVER_LOG}" >&2 || true
  exit 1
}

wait_for_cloudflared_url() {
  local i
  for i in {1..30}; do
    local url
    url="$(python3 - <<'PY' "${TUNNEL_LOG}"
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("")
    raise SystemExit(0)
text = path.read_text(encoding="utf-8", errors="ignore")
matches = re.findall(r"https://[-a-zA-Z0-9.]+trycloudflare\\.com", text)
print(matches[-1] if matches else "")
PY
)"
    if [[ -n "${url}" ]]; then
      printf '%s\n' "${url}"
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_ngrok_url() {
  local i
  for i in {1..30}; do
    local url
    url="$(curl -fsS http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 - <<'PY'
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)

for item in data.get("tunnels", []):
    public_url = item.get("public_url", "")
    if public_url.startswith("https://"):
        print(public_url)
        break
else:
    print("")
PY
)"
    if [[ -n "${url}" ]]; then
      printf '%s\n' "${url}"
      return 0
    fi
    sleep 1
  done
  return 1
}

start_server() {
  require_cmd curl
  echo "启动企业微信客服测试服务: http://${HOST}:${PORT}"
  (
    cd "${WORKDIR}"
    ./.venv/bin/python -m uvicorn app.src.wecom.demo_app:app --host "${HOST}" --port "${PORT}"
  ) >"${SERVER_LOG}" 2>&1 &
  SERVER_PID=$!
  wait_for_health
}

start_cloudflared() {
  : >"${TUNNEL_LOG}"
  echo "检测到 cloudflared，正在创建公网地址..." >&2
  "${LOCAL_CLOUDFLARED:-cloudflared}" tunnel --url "http://${HOST}:${PORT}" --no-autoupdate >"${TUNNEL_LOG}" 2>&1 &
  TUNNEL_PID=$!
  PUBLIC_BASE_URL="$(wait_for_cloudflared_url)"
}

start_ngrok() {
  : >"${TUNNEL_LOG}"
  echo "检测到 ngrok，正在创建公网地址..." >&2
  ngrok http "${PORT}" >"${TUNNEL_LOG}" 2>&1 &
  TUNNEL_PID=$!
  PUBLIC_BASE_URL="$(wait_for_ngrok_url)"
}

print_missing_tunnel_help() {
  cat <<EOF
未检测到可用的公网穿透工具。

你可以先安装以下任一工具，然后重新运行本脚本：

1. cloudflared
   macOS:
   brew install cloudflared

2. ngrok
   macOS:
   brew install ngrok/ngrok/ngrok

安装后，本脚本会自动输出企业微信后台应填写的回调地址。
当前本地服务仍然已经启动:
  http://${HOST}:${PORT}
EOF
}

start_server

if [[ -x "${LOCAL_CLOUDFLARED}" ]]; then
  start_cloudflared || true
elif command -v cloudflared >/dev/null 2>&1; then
  LOCAL_CLOUDFLARED="$(command -v cloudflared)"
  start_cloudflared || true
elif command -v ngrok >/dev/null 2>&1; then
  start_ngrok || true
else
  print_missing_tunnel_help
  wait
  exit 0
fi

if [[ -z "${PUBLIC_BASE_URL}" ]]; then
  echo "公网地址创建失败，请查看日志: ${TUNNEL_LOG}" >&2
  tail -n 50 "${TUNNEL_LOG}" >&2 || true
  exit 1
fi

cat <<EOF

公网地址已创建:
  ${PUBLIC_BASE_URL}

企业微信后台请填写:
  回调 URL: ${PUBLIC_BASE_URL}${CALLBACK_PATH}

本地健康检查:
  http://${HOST}:${PORT}/health

调试接口:
  ${PUBLIC_BASE_URL}/wecom/kf/callbacks

日志文件:
  服务日志: ${SERVER_LOG}
  穿透日志: ${TUNNEL_LOG}

按 Ctrl+C 可同时关闭本地服务和公网穿透。
EOF

wait
