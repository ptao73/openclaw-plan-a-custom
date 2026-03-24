"""统一 LLM 调用接口 - 兼容 OpenAI API 格式的各类模型"""
from __future__ import annotations
import json
import logging
import httpx
from typing import Any
from .config import ModelConfig

logger = logging.getLogger("openclaw.llm")


class LLMClient:
    """
    统一的 LLM 客户端，支持所有 OpenAI 兼容 API：
    - DeepSeek
    - Moonshot / Kimi
    - Qwen (DashScope 兼容模式)
    - OpenAI
    """

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout

    async def chat(
        self,
        model_config: ModelConfig,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str:
        """发送聊天请求并返回文本结果"""
        url = f"{model_config.base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config.api_key}",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "messages": messages,
            "max_tokens": model_config.max_tokens,
            "temperature": temperature,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        logger.info(f"调用模型: {model_config.model_name} ({model_config.provider})")
        logger.debug(f"Prompt 长度: system={len(system_prompt)}, user={len(user_message)}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                logger.info(
                    f"模型返回: {len(content)} 字符, "
                    f"tokens={usage.get('total_tokens', '?')}"
                )
                return content

            except httpx.HTTPStatusError as e:
                logger.error(f"API 错误 [{e.response.status_code}]: {e.response.text[:200]}")
                raise
            except httpx.TimeoutException:
                logger.error(f"模型调用超时 ({self.timeout}s)")
                raise
            except Exception as e:
                logger.error(f"调用失败: {e}")
                raise

    async def chat_json(
        self,
        model_config: ModelConfig,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """
        调用模型并解析 JSON 响应。
        先尝试 json_mode，如果 provider 不支持则手动解析。
        """
        # 在 system prompt 中强调返回 JSON
        enhanced_prompt = (
            system_prompt + "\n\n"
            "重要：你的回复必须是纯 JSON 格式，不要包含 markdown 代码块标记或其他文字。"
        )

        raw = await self.chat(
            model_config=model_config,
            system_prompt=enhanced_prompt,
            user_message=user_message,
            temperature=temperature,
            json_mode=False,  # 不是所有 provider 都支持
        )

        return self._parse_json(raw)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """从模型响应中提取 JSON，容忍 markdown 包裹"""
        cleaned = text.strip()

        # 去除 markdown 代码块
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 去掉首行 ```json 和末行 ```
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[start:end]).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试找到第一个 { 和最后一个 }
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                try:
                    return json.loads(cleaned[first_brace : last_brace + 1])
                except json.JSONDecodeError:
                    pass
            # 无法解析，返回原文包装
            return {"_raw": text, "_parse_error": True}


# 全局 LLM 客户端
llm = LLMClient()
