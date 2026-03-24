#!/bin/bash
# backup.sh - 备份配置和工作区
BACKUP_DIR="/opt/openclaw/versions"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"

echo "[OpenClaw] 创建备份: $BACKUP_FILE"
tar -czf "$BACKUP_FILE" \
  -C /opt/openclaw \
  instance/config \
  instance/workspace \
  current \
  --exclude='current/.venv'

echo "[OpenClaw] 备份完成: $(du -h "$BACKUP_FILE" | cut -f1)"

# 保留最近 10 个备份
cd "$BACKUP_DIR"
ls -1t backup_*.tar.gz | tail -n +11 | xargs -r rm
echo "[OpenClaw] 清理旧备份完成"
