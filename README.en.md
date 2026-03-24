# Plan A: Custom Python Multi-Agent Controller

[中文](README.md) | [English](README.en.md)

> Status: designed and deployable. The production deployment ultimately moved to Plan B based on official OpenClaw.

This project is a pure Python multi-agent controller that does not depend on any third-party agent framework. It includes a custom pipeline engine, unified LLM client, Telegram bot integration, and a reserved interface for future remote workers.

This repository is packaged as a standalone GitHub project. It does not contain real API keys, bot tokens, or server credentials. Sensitive values are injected through environment variables.

## Highlights

- No external agent framework dependency
- Readable and fully controllable pipeline orchestration
- Unified client for DeepSeek, Moonshot, Qwen, and OpenAI-compatible APIs
- Built-in Planner / Researcher / Executor / Reviewer collaboration flow
- Remote worker routing reserved for future multi-node expansion

## Architecture

```text
Telegram Bot
    -> Pipeline Engine
       -> Planner
       -> Researcher
       -> Executor
       -> Reviewer
    -> Unified LLM Client
```

## Core Files

| File | Purpose |
|------|---------|
| `core/openclaw/pipeline.py` | Pipeline orchestration for the four-agent workflow |
| `core/openclaw/llm.py` | Unified LLM client for OpenAI-compatible APIs |
| `core/openclaw/config.py` | Configuration loading for roles, models, and remote workers |
| `core/openclaw/models.py` | Data models for tasks, plans, steps, and reviews |
| `core/openclaw/telegram_bot.py` | Telegram bot integration |
| `core/openclaw/main.py` | Entry point |
| `config/openclaw.json` | Main application configuration |
| `config/remote-workers.json` | Reserved remote worker configuration |
| `roles/*.md` | System prompts for each role |
| `setup.sh` | Deployment script |

## Pipeline Flow

```python
async def run(task):
    plan = await planner.analyze(task)

    for step in plan.steps:
        if step.assigned_to == "researcher":
            result = await researcher.execute(step)
        else:
            result = await executor.execute(step)

    review = await reviewer.check(results)
    while review.needs_rework and rework_count < 2:
        rework_failed_steps()
        review = await reviewer.check(results)

    return review.final_output
```

## Configuration Example

### Role Configuration

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

### Model Configuration

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

## Deployment

```bash
# 1. Upload the repository to the server
scp -r openclaw-plan-a-custom/ root@SERVER:/opt/openclaw-src/

# 2. Run the deployment script
ssh root@SERVER
cd /opt/openclaw-src/openclaw-plan-a-custom
bash setup.sh

# 3. Configure API keys
nano /opt/openclaw/instance/scripts/env.sh

# 4. Start the service
/opt/openclaw/instance/scripts/start.sh
```

## Relationship to Plan B

Plan A was the first design iteration before the production setup moved to official OpenClaw.

Its main value is:

1. A complete custom pipeline design that can be used as a standalone project.
2. A reusable unified LLM client for multiple providers.
3. Prompt templates that can be migrated into other frameworks.
4. A routing design that informed the later multi-node Plan B architecture.

Plan B was ultimately chosen because OpenClaw already provided gateway management, channel integration, and workspace handling.

## Related Documents

- Deployment lessons: [LESSONS.md](LESSONS.md)
- For the production-oriented dual-node deployment, see the public repository `openclaw-plan-b-official`
