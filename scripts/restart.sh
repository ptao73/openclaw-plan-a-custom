#!/bin/bash
# restart.sh - 重启 OpenClaw
echo "[OpenClaw] 重启中..."
systemctl restart openclaw
sleep 2
systemctl status openclaw --no-pager
