#!/bin/bash
# start.sh - 启动 OpenClaw
source /opt/openclaw/instance/scripts/env.sh
echo "[OpenClaw] 启动中..."
systemctl start openclaw
sleep 2
systemctl status openclaw --no-pager
