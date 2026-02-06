import asyncio
import json
import os
import time
import random
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI



class AsyncLLMAgent:
    def __init__(
            self,
            model=os.getenv("LLM_CHAT_CHECK_MODEL") or "gemini-2.5-flash",
    ):
        env_path = Path(".env")
        load_dotenv(env_path)
        # 默认初始系统提示词
        self.system_prompt = "You are a kind robot whose purpose is to engage in casual conversation and liven up the atmosphere in a group chat, depending on the context."
        self.client = AsyncOpenAI(api_key=os.getenv(
            "OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.model = model

    async def built_language_recognize(self, context) -> str:
        prompt_template = """
        Please return the primary language type for the context provided.
        [Context]
        {context}

        Only output one of the following: 
        [
        zh
        zh-CN
        zh-Hans
        id
        th
        tl
        fil
        ms
        vi
        es
        pt
        fr
        ja
        Nihongo
        ko
        Hangugeo
        ]

        Do not return anything else.
        """
        prompt = prompt_template.format(
            context=context,
        )
        return prompt

    # 根据不同的语言使用不同的提示词
    async def get_module_prompt_by_language_type(self, module, language_type):
        if module == "chat":
            # 读取 json 文件
            with open("classify/generate_language_template/chat_language_prompt.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[language_type]
        if module == "welcome":
            with open("classify/generate_language_template/welcome_language_prompt.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[language_type]
        if module == "ignore":
            with open("classify/generate_language_template/ignore_language_prompt.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[language_type]
        if module == "warm":
            with open("classify/generate_language_template/warm_language_prompt.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[language_type]

    async def generate_reply(self, user_prompt: str):
        result = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return result.choices[0].message.content.strip()
