"""DataInterpretProcessor：LLM 数据解读（流式）。

V1.0 新增模块。
"""

from __future__ import annotations

import json
import os
from typing import AsyncGenerator

from models import QueryResult


async def interpret(query: str, result: QueryResult) -> AsyncGenerator[str, None]:
    """用 DeepSeek 流式解读查询结果。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        yield "（配置 DEEPSEEK_API_KEY 可开启 AI 数据解读）"
        return

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

        # 取 top 10 行
        rows_sample = result.rows[:10]
        cols = [c.name for c in result.columns]

        prompt = f"""#Role: 数据分析师
#Task: 用 2-3 句话解读数据，引用关键数字。

#问题: {query}
#列: {cols}
#数据 (前10行): {json.dumps([dict(zip(cols, row)) for row in rows_sample], ensure_ascii=False)}

用中文回答，简洁直接:"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
            stream=True,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"（解读生成失败: {e}）"
