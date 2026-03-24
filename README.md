# Plan A: 自定义 Python 多角色中控系统

[中文](README.md) | [English](README.en.md)

> 状态：已设计完成，可部署。最终选择了 Plan B (OpenClaw 官方) 上线。

纯 Python 实现的四角色协作系统，不依赖任何第三方 agent 框架。完全自建 pipeline 引擎、LLM 客户端、Telegram Bot。

本仓库已经整理为可独立发布的 GitHub 项目。仓库中不包含真实 API Key、Bot Token 或服务器凭据，所有敏感信息都通过环境变量注入。

## 项目亮点

- 不依赖第三方 agent 框架，核心流程全部可读、可改、可控
- 统一兼容 DeepSeek、Moonshot、Qwen、OpenAI 兼容接口
- 内置 Planner / Researcher / Executor / Reviewer 四角色协作流
- 预留远程 worker 路由接口，方便后续扩展为多节点架构
- 适合作为多角色 agent pipeline 的学习样例和二次开发基础

## 架构

```
┌──────────────────────────────────────────────┐
│                 Telegram Bot                  │
│            (python-telegram-bot)              │
└──────────────────┬───────────────────────────┘
                   │ /task 命令
                   ▼
┌──────────────────────────────────────────────┐
│              Pipeline Engine                  │
│                                              │
│  1. Planner   → 分析意图、拆解步骤           │
│  2. Researcher → 信息搜集                    │
│     Executor  → 任务执行（并行/串行）         │
│  3. Reviewer  → 质量审查                     │
│  4. 反馈循环  → 不合格则返工（最多2轮）       │
└──────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│           统一 LLM 客户端                     │
│  支持: DeepSeek / Moonshot / Qwen / OpenAI   │
│  (OpenAI-compatible API 格式)                 │
└──────────────────────────────────────────────┘
```

## 核心文件说明

| 文件 | 作用 |
|------|------|
| `core/openclaw/pipeline.py` | 核心管线引擎，编排四角色协作 |
| `core/openclaw/llm.py` | 统一 LLM 客户端，兼容多家 API |
| `core/openclaw/config.py` | 配置管理（角色、模型、远程 worker） |
| `core/openclaw/models.py` | 数据模型（Task、Plan、Step、Review） |
| `core/openclaw/telegram_bot.py` | Telegram 接口 |
| `core/openclaw/main.py` | 入口 |
| `config/openclaw.json` | 主配置文件 |
| `config/remote-workers.json` | 远程 worker 配置（预留） |
| `roles/*.md` | 四个角色的 system prompt |
| `setup.sh` | 一键部署脚本 |

## Pipeline 流程详解

```python
async def run(task):
    # Phase 1: Planning
    plan = await planner.analyze(task)     # 拆解为步骤列表

    # Phase 2: Execution
    for step in plan.steps:
        if step.assigned_to == "researcher":
            result = await researcher.execute(step)
        else:
            result = await executor.execute(step)

    # Phase 3: Review + Feedback Loop
    review = await reviewer.check(results)
    while review.needs_rework and rework_count < 2:
        rework_failed_steps()
        review = await reviewer.check(results)

    return review.final_output
```

## 配置示例

### 角色配置 (openclaw.json)
```json
{
  "roles": {
    "planner": {
      "enabled": true,
      "prompt_file": "roles/planner.md",
      "model": "deepseek-chat",
      "timeout_seconds": 30
    },
    "executor": {
      "enabled": true,
      "prompt_file": "roles/executor.md",
      "model": "deepseek-chat",
      "allowed_tools": ["shell", "file_io", "http_request", "model_call"],
      "sandbox": true
    }
  },
  "pipeline": {
    "default_flow": ["planner", "researcher|executor", "reviewer"],
    "max_iterations": 5,
    "enable_feedback_loop": true
  }
}
```

### 模型配置
```json
{
  "models": {
    "deepseek-chat": {
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "model_name": "deepseek-chat",
      "api_key_env": "DEEPSEEK_API_KEY"
    },
    "qwen-turbo": {
      "provider": "dashscope",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "model_name": "qwen-turbo",
      "api_key_env": "QWEN_API_KEY"
    }
  }
}
```

## 部署

```bash
# 1. 上传仓库到服务器
scp -r openclaw-plan-a-custom/ root@SERVER:/opt/openclaw-src/

# 2. 执行部署脚本
ssh root@SERVER
cd /opt/openclaw-src/openclaw-plan-a-custom
bash setup.sh

# 3. 配置 API Key
nano /opt/openclaw/instance/scripts/env.sh

# 4. 启动
/opt/openclaw/instance/scripts/start.sh
```

## 与 Plan B 的关系

Plan A 是第一版设计，当时还没有深入使用 OpenClaw 官方框架。它的价值在于：

1. **完整的 pipeline 引擎设计**：可作为独立项目使用
2. **统一 LLM 客户端**：兼容多家国产 API，可复用
3. **角色 prompt 模板**：planner/executor/researcher/reviewer 的 prompt 可直接移植到其他框架
4. **远程 worker 接口预留**：虽未实现，但设计思路被 Plan B 采纳

最终选择 Plan B 的原因：OpenClaw 已经提供了 gateway、channel adapter、workspace 管理等基础设施，重复造轮子不划算。

## 相关文档

- 踩坑记录见 [LESSONS.md](LESSONS.md)
- 如果你更关注生产可用的双节点部署，可以看公开仓库 `openclaw-plan-b-official`
