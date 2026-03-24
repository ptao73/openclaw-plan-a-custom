"""Telegram Bot 接口 - 用户与 OpenClaw 交互的主入口"""
from __future__ import annotations
import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from .config import config
from .models import Task
from .pipeline import Pipeline

logger = logging.getLogger("openclaw.telegram")

pipeline = Pipeline()


def _is_authorized(chat_id: int) -> bool:
    allowed = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not allowed:
        return True  # 未配置则允许所有（开发阶段）
    return str(chat_id) in [s.strip() for s in allowed.split(",")]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🤖 OpenClaw 中控已就绪\n\n"
        "发送任何消息即可开始任务\n"
        "命令：\n"
        "/task <描述> - 提交任务\n"
        "/status - 当前状态\n"
        "/config - 配置摘要"
    )


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update.effective_chat.id):
        return

    text = update.message.text.replace("/task", "", 1).strip()
    if not text:
        await update.message.reply_text("请描述你的任务，例如：/task 查询最新的 AI 论文")
        return

    await _process_task(update, text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update.effective_chat.id):
        return

    workers = config.get_active_workers()
    worker_info = (
        "\n".join(f"  ✅ {w.name}" for w in workers)
        if workers else "  ❌ 无可用 worker"
    )

    roles_info = "\n".join(
        f"  {'✅' if r.enabled else '❌'} {r.name} → {r.model}"
        for r in config.roles.values()
    )

    await update.message.reply_text(
        f"📊 OpenClaw 状态\n\n"
        f"角色:\n{roles_info}\n\n"
        f"远程 Worker:\n{worker_info}"
    )


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update.effective_chat.id):
        return

    models_info = "\n".join(
        f"  {name}: {m.provider}/{m.model_name}"
        for name, m in config.models.items()
    )

    await update.message.reply_text(
        f"⚙️ 配置摘要\n\n"
        f"可用模型:\n{models_info}\n\n"
        f"管线流程: {config.pipeline.get('default_flow', [])}\n"
        f"最大迭代: {config.pipeline.get('max_iterations', 5)}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理普通消息，当作任务提交"""
    if not _is_authorized(update.effective_chat.id):
        return
    if not update.message or not update.message.text:
        return

    await _process_task(update, update.message.text)


async def _process_task(update: Update, user_input: str):
    """创建并执行任务"""
    task = Task(user_input=user_input, source="telegram")

    # 发送确认消息
    status_msg = await update.message.reply_text(
        f"📋 任务已接收 [{task.task_id}]\n"
        f"正在规划..."
    )

    try:
        # 执行管线
        task = await pipeline.run(task)

        # 发送结果
        if task.review and task.review.final_output:
            output = task.review.final_output
        elif task.error:
            output = f"❌ 任务失败: {task.error}"
        else:
            output = "任务已完成，但没有产出具体输出。"

        # Telegram 消息长度限制 4096
        if len(output) > 4000:
            output = output[:4000] + "\n\n...(输出过长，已截断)"

        await status_msg.edit_text(
            f"{'✅' if task.status.value == 'completed' else '❌'} "
            f"任务 [{task.task_id}]\n\n{output}"
        )

    except Exception as e:
        logger.error(f"任务处理异常: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ 处理异常: {e}")


def create_bot() -> Application:
    """创建并配置 Telegram Bot"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("未设置 TELEGRAM_BOT_TOKEN 环境变量")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
