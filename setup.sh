#!/bin/bash
# ============================================================
# OpenClaw 单实例中控 - 初始化部署脚本
# 目标服务器: 阿里云 ECS 香港 (Ubuntu 24.04)
# ============================================================

set -e

BASE="/opt/openclaw"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[OpenClaw]${NC} $1"; }
warn() { echo -e "${YELLOW}[Warning]${NC} $1"; }

# ---- 1. 创建目录结构 ----
log "创建目录结构..."

dirs=(
  "$BASE/current"
  "$BASE/versions"
  "$BASE/instance/config/roles"
  "$BASE/instance/workspace/shared"
  "$BASE/instance/workspace/planner"
  "$BASE/instance/workspace/executor"
  "$BASE/instance/workspace/researcher"
  "$BASE/instance/workspace/reviewer"
  "$BASE/instance/logs"
  "$BASE/instance/run"
  "$BASE/instance/scripts"
)

for d in "${dirs[@]}"; do
  mkdir -p "$d"
done

log "目录结构创建完成 ✓"

# ---- 2. 复制核心文件 ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log "复制配置文件..."
cp "$SCRIPT_DIR/config/openclaw.json"        "$BASE/instance/config/"
cp "$SCRIPT_DIR/config/remote-workers.json"  "$BASE/instance/config/"

log "复制角色定义..."
cp "$SCRIPT_DIR/roles/"*.md                  "$BASE/instance/config/roles/"

log "复制管理脚本..."
cp "$SCRIPT_DIR/scripts/"*.sh                "$BASE/instance/scripts/"
chmod +x "$BASE/instance/scripts/"*.sh

log "复制核心程序..."
cp -r "$SCRIPT_DIR/core/"*                   "$BASE/current/"

# ---- 3. 创建 Python 虚拟环境 ----
log "创建 Python 虚拟环境..."
if ! command -v python3 &>/dev/null; then
  warn "未检测到 python3，请先安装: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

python3 -m venv "$BASE/current/.venv"
source "$BASE/current/.venv/bin/activate"

log "安装依赖..."
pip install --upgrade pip -q
pip install -r "$BASE/current/requirements.txt" -q

deactivate

# ---- 4. 创建 env.sh (如果不存在) ----
ENV_FILE="$BASE/instance/scripts/env.sh"
if [ ! -f "$ENV_FILE" ] || ! grep -q "ALREADY_CONFIGURED" "$ENV_FILE"; then
  log "生成 env.sh 模板（请编辑填入 API Key）..."
  cat > "$ENV_FILE" << 'ENVEOF'
#!/bin/bash
# ============================================================
# OpenClaw 环境变量 - 请填入你的实际 API Key
# ============================================================
# ALREADY_CONFIGURED=true  # 填完后取消此行注释

export OPENCLAW_BASE="/opt/openclaw"
export OPENCLAW_CONFIG="$OPENCLAW_BASE/instance/config/openclaw.json"
export OPENCLAW_LOG_DIR="$OPENCLAW_BASE/instance/logs"

# --- AI 模型 API ---
export MOONSHOT_API_KEY=""          # Kimi / Moonshot
export QWEN_API_KEY=""              # 通义千问 (DashScope)
export DEEPSEEK_API_KEY=""          # DeepSeek
export OPENAI_API_KEY=""            # OpenAI (可选, 通过 AWS worker)
export ANTHROPIC_API_KEY=""         # Claude API (可选)

# --- Telegram Bot ---
export TELEGRAM_BOT_TOKEN=""
export TELEGRAM_CHAT_ID=""

# --- 远程 Worker (未来启用) ---
export AWS_WORKER_URL=""
export AWS_WORKER_TOKEN=""
ENVEOF
  chmod 600 "$ENV_FILE"
fi

# ---- 5. 创建 systemd 服务文件 ----
log "生成 systemd 服务文件..."
cat > "/tmp/openclaw.service" << 'SVCEOF'
[Unit]
Description=OpenClaw Multi-Agent Control Center
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/openclaw/current
EnvironmentFile=/opt/openclaw/instance/scripts/env.sh
ExecStart=/opt/openclaw/current/.venv/bin/python -m openclaw.main
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=append:/opt/openclaw/instance/logs/openclaw.log
StandardError=append:/opt/openclaw/instance/logs/openclaw-error.log

[Install]
WantedBy=multi-user.target
SVCEOF

if [ -d /etc/systemd/system ]; then
  cp /tmp/openclaw.service /etc/systemd/system/
  systemctl daemon-reload
  log "systemd 服务已注册 (尚未启动)"
fi

# ---- 6. 完成 ----
echo ""
log "=========================================="
log "  OpenClaw 部署完成！"
log "=========================================="
echo ""
echo "  目录结构:  $BASE/"
echo "  核心程序:  $BASE/current/"
echo "  配置文件:  $BASE/instance/config/"
echo "  角色定义:  $BASE/instance/config/roles/"
echo ""
echo "  下一步操作:"
echo "  1. 编辑 API Key:  nano $BASE/instance/scripts/env.sh"
echo "  2. 启动服务:      $BASE/instance/scripts/start.sh"
echo "  3. 查看状态:      $BASE/instance/scripts/status.sh"
echo "  4. 查看日志:      tail -f $BASE/instance/logs/openclaw.log"
echo ""
