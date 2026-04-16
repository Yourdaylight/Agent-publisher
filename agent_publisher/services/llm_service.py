from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


class LLMAdapter(ABC):
    @abstractmethod
    async def generate(
        self, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> str: ...

    async def generate_stream(
        self, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response chunk by chunk. Default falls back to non-streaming."""
        result = await self.generate(model, api_key, messages, base_url)
        yield result


class ClaudeAdapter(LLMAdapter):
    async def generate(
        self, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> str:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)
        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        resp = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_msg if system_msg else anthropic.NOT_GIVEN,
            messages=user_messages,
        )
        return resp.content[0].text


class OpenAIAdapter(LLMAdapter):
    async def generate(
        self, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
        resp = await client.chat.completions.create(model=model, messages=messages)
        return resp.choices[0].message.content or ""

    async def generate_stream(
        self, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
        stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


class MiniMaxAdapter(LLMAdapter):
    """MiniMax API adapter using their OpenAI-compatible endpoint."""

    BASE_URL = "https://api.minimax.chat/v1"

    async def generate(
        self, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


_ADAPTERS: dict[str, LLMAdapter] = {
    "claude": ClaudeAdapter(),
    "openai": OpenAIAdapter(),
    "minimax": MiniMaxAdapter(),
}


class LLMService:
    @staticmethod
    async def generate(
        provider: str, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> str:
        """Unified LLM call entry point. Routes to the appropriate provider adapter."""
        adapter = _ADAPTERS.get(provider)
        if not adapter:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        logger.info("LLM call: provider=%s model=%s", provider, model)
        return await adapter.generate(model, api_key, messages, base_url=base_url)

    @staticmethod
    def generate_stream(
        provider: str, model: str, api_key: str, messages: list[dict], base_url: str = ""
    ) -> AsyncGenerator[str, None]:
        """Unified streaming LLM call. Returns an async generator of text chunks."""
        adapter = _ADAPTERS.get(provider)
        if not adapter:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        logger.info("LLM stream call: provider=%s model=%s", provider, model)
        return adapter.generate_stream(model, api_key, messages, base_url=base_url)

    # Output format instruction appended when not present in the prompt
    OUTPUT_FORMAT = (
        "请按以下格式输出：\n---TITLE---\n文章标题\n---DIGEST---\n摘要\n---CONTENT---\nMarkdown正文"
    )

    @staticmethod
    def _load_base_prompt() -> str:
        """Load the base prompt from ``agent_publisher/prompt/base_prompt.md``.

        Uses an lru_cache internally so the file is read only once.
        """
        from agent_publisher.prompt import load_base_prompt

        return load_base_prompt()

    @staticmethod
    def build_article_messages(
        topic: str,
        news_list: str,
        prompt_template: str,
        agent_description: str,
    ) -> list[dict]:
        """Build messages for article generation.

        Prompt layering:
          1. **base_prompt** (from ``prompt/base_prompt.md``) — always included
             as the foundation of the system prompt.
          2. **agent_description** — appended after base prompt to add
             agent-specific vertical context (persona, expertise, style).
          3. If neither is available, a sensible default referencing
             ``topic`` is used as fallback.

        Guarantees that material content (news_list) is ALWAYS included in
        the user message, even when the prompt template doesn't contain a
        ``{news_list}`` placeholder.
        """
        base_prompt = LLMService._load_base_prompt()

        if agent_description and base_prompt:
            # Layer: base prompt + agent-specific context
            system_prompt = f"{base_prompt}\n\n---\n\n## 当前身份设定\n\n{agent_description}"
        elif agent_description:
            # No base prompt file — agent description alone
            system_prompt = agent_description
        elif base_prompt:
            # Base prompt + topic context (no agent description)
            system_prompt = (
                f"{base_prompt}\n\n---\n\n"
                f"## 当前任务\n\n你当前专注于「{topic}」领域的内容创作。"
                f"请结合该领域的行业背景和受众特点来撰写文章。"
            )
        else:
            # Fallback: no base prompt, no agent description
            system_prompt = (
                f"你是一个专注于「{topic}」领域的资深公众号编辑。"
                "你擅长将热点新闻和素材整合为一篇有深度、有观点的公众号文章。"
                "你的文章特点：标题精炼吸引人、开头有力、观点鲜明、结构清晰、适合微信公众号阅读。"
            )

        if prompt_template:
            # Check if template explicitly includes material content placeholder
            has_news_placeholder = "{news_list}" in prompt_template

            # Safe format: handle stray braces in templates gracefully
            try:
                user_prompt = prompt_template.format(
                    topic=topic,
                    news_list=news_list,
                    style="公众号文章",
                )
            except (KeyError, ValueError, IndexError):
                # Template has stray braces or unknown keys — use as-is
                user_prompt = prompt_template
                has_news_placeholder = False

            # CRITICAL: If template didn't include {news_list}, append
            # material content so LLM always sees the source material.
            if not has_news_placeholder and news_list:
                user_prompt += (
                    f"\n\n---\n以下是参考素材：\n\n{news_list}\n\n"
                    "请基于以上素材，撰写一篇公众号文章。要求：\n"
                    "1. 标题吸引人，适合公众号传播\n"
                    "2. 内容有深度分析，不只是新闻堆砌\n"
                    "3. 使用 Markdown 格式\n"
                    "4. 文章开头给出一段简短摘要（用于公众号摘要）\n"
                    "5. 文末总结观点\n"
                    "6. 字数 1500-3000 字"
                )

            # Ensure output format instruction is always present
            if "---TITLE---" not in user_prompt:
                user_prompt += f"\n\n{LLMService.OUTPUT_FORMAT}"
        else:
            user_prompt = (
                f"以下是今天关于「{topic}」的热点新闻：\n\n{news_list}\n\n"
                "请基于以上新闻，撰写一篇公众号文章。要求：\n"
                "1. 标题吸引人，适合公众号传播\n"
                "2. 内容有深度分析，不只是新闻堆砌\n"
                "3. 使用 Markdown 格式\n"
                "4. 文章开头给出一段简短摘要（用于公众号摘要）\n"
                "5. 文末总结观点\n"
                "6. 字数 1500-3000 字\n\n"
                f"{LLMService.OUTPUT_FORMAT}"
            )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def parse_article_response(text: str) -> dict:
        """Parse LLM response into title, digest, and content."""
        result = {"title": "", "digest": "", "content": text}

        if "---TITLE---" in text:
            parts = text.split("---TITLE---", 1)
            remaining = parts[1] if len(parts) > 1 else ""

            if "---DIGEST---" in remaining:
                title_part, remaining = remaining.split("---DIGEST---", 1)
                result["title"] = title_part.strip()

                if "---CONTENT---" in remaining:
                    digest_part, content_part = remaining.split("---CONTENT---", 1)
                    result["digest"] = digest_part.strip()
                    result["content"] = content_part.strip()
                else:
                    result["digest"] = remaining.strip()
            else:
                result["title"] = remaining.strip()

        return result
