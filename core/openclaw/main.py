"""OpenClaw 主入口"""
import asyncio
import logging
import sys
from pathlib import Path

from .config import config, LOGS_DIR
from .telegram_bot import create_bot


def setup_logging():
    """配置日志"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    log_cfg = config._raw.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO"))
    fmt = log_cfg.get("format", "%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # 控制台 + 文件双输出
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "openclaw.log", encoding="utf-8"),
    ]

    logging.basicConfig(level=level, format=fmt, handlers=handlers)

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main():
    """启动 OpenClaw"""
    # 加载配置
    config.load()
    setup_logging()

    logger = logging.getLogger("openclaw.main")
    logger.info("=" * 50)
    logger.info("OpenClaw 多角色中控系统启动")
    logger.info(f"角色: {list(config.roles.keys())}")
    logger.info(f"模型: {list(config.models.keys())}")
    logger.info(f"远程 Worker: {[w.name for w in config.get_active_workers()]}")
    logger.info("=" * 50)

    # 检查关键配置
    if not any(m.api_key for m in config.models.values()):
        logger.error("没有配置任何可用的 API Key！请编辑 env.sh")
        sys.exit(1)

    # 启动模式
    if config.telegram.get("enabled"):
        logger.info("启动 Telegram Bot 模式...")
        bot = create_bot()
        bot.run_polling(drop_pending_updates=True)
    else:
        logger.info("Telegram 未启用，进入 CLI 模式...")
        asyncio.run(cli_mode())


async def cli_mode():
    """命令行交互模式（Telegram 未启用时的备选）"""
    from .models import Task
    from .pipeline import Pipeline

    pipeline = Pipeline()
    logger = logging.getLogger("openclaw.cli")

    print("\n🤖 OpenClaw CLI 模式 (输入 quit 退出)\n")

    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        task = Task(user_input=user_input, source="cli")
        task = await pipeline.run(task)

        if task.review and task.review.final_output:
            print(f"\n📋 {task.review.final_output}\n")
        elif task.error:
            print(f"\n❌ {task.error}\n")
        else:
            print(f"\n{task.to_summary()}\n")


if __name__ == "__main__":
    main()
