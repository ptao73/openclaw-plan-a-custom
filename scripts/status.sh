#!/bin/bash
# status.sh - 查看 OpenClaw 状态
echo "========== OpenClaw 状态 =========="
systemctl status openclaw --no-pager 2>/dev/null || echo "服务未注册"
echo ""
echo "========== 最近日志 (10行) =========="
tail -10 /opt/openclaw/instance/logs/openclaw.log 2>/dev/null || echo "暂无日志"
echo ""
echo "========== 磁盘使用 =========="
du -sh /opt/openclaw/ 2>/dev/null
echo ""
echo "========== 进程检查 =========="
pgrep -f "openclaw.main" > /dev/null && echo "主进程: 运行中" || echo "主进程: 未运行"
