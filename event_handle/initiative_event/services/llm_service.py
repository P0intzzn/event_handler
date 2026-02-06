"""
LLM 调用服务模块

提供 LLM 对话生成、语言识别等功能
"""
from typing import Optional
from openai import AsyncOpenAI

from const import DEFAULT_LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL


class AsyncLLMAgent:
    """
    异步 LLM 代理类
    
    封装 OpenAI 客户端，提供对话生成和语言识别功能
    """
    
    def __init__(self, model: Optional[str] = None):
        """
        初始化 LLM 代理
        
        Args:
            model: LLM 模型名称，默认使用 DEFAULT_LLM_MODEL
        """
        self.system_prompt = "You are a kind robot whose purpose is to engage in casual conversation and liven up the atmosphere in a group chat, depending on the context."
        self.client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        self.model = model or DEFAULT_LLM_MODEL

    @staticmethod
    async def built_language_recognize(context: str) -> str:
        """
        构建语言识别 Prompt
        
        Args:
            context: 需要识别语言的文本上下文
        
        Returns:
            str: 语言识别 Prompt
        """
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
        en
        ]

        Do not return anything else.
        """
        return prompt_template.format(context=context)
    
    async def generate_reply(self, user_prompt: str) -> str:
        """生成对话回复

        Args:
            user_prompt: 用户提示词

        Returns:
            str: LLM 生成的回复内容

        Examples:
            - agent = AsyncLLMAgent()
            - reply = await agent.generate_reply("Hello!")
            - isinstance(reply, str)
            - True
        """

        result = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return result.choices[0].message.content.strip()
    
    async def recognize_language(self, context: str) -> str:
        """
        识别文本语言类型

        Args:
            context: 需要识别语言的文本

        Returns:
            str: 语言代码（zh, en, ja 等）

        Examples:
            - agent = AsyncLLMAgent()
            - lang = await agent.recognize_language("你好世界")
            - lang in ["zh", "zh-CN", "zh-Hans"]
            - True
        """

        prompt = await self.built_language_recognize(context)
        language_code = await self.generate_reply(prompt)
        return language_code
