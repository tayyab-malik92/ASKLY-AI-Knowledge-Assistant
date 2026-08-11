import json
from groq import Groq
from app.core.config import settings

class LLMClient:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.LLM_MODEL

    def call_with_tools(self, messages: list, tools: list):
        """Calls the LLM passing system/user messages and available function tools."""
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        ).choices[0].message

    def call_json_schema(self, prompt: str, system_prompt: str = "") -> dict:
        """Forces the LLM to respond strictly in valid JSON format."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

llm_client = LLMClient()