import json
import logging

from groq import Groq
from app.core.config import settings


logger = logging.getLogger("askly.llm_client")


class LLMClient:

    def __init__(self):
        self.client = Groq(
            api_key=settings.GROQ_API_KEY
        )

        self.model = settings.LLM_MODEL

    # ==============================================================
    # NORMAL LLM CALL
    # ==============================================================

    def call(
        self,
        messages: list,
        temperature: float = 0.0,
    ):
        """
        Normal LLM call.

        Used for:
        - PDF/RAG answers
        - summaries
        - normal text generation

        IMPORTANT:
        This call does NOT send tools or tool_choice.
        """

        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        ).choices[0].message

    # ==============================================================
    # TOOL-CALLING LLM
    # ==============================================================

    def call_with_tools(
        self,
        messages: list,
        tools: list | None = None,
        temperature: float = 0.0,
    ):
        """
        LLM call with optional tools.

        If tools are empty/None, this automatically falls back
        to the normal LLM call.

        This is VERY important because Groq should not receive:

            tools=[]
            tool_choice="auto"

        for a normal PDF question.
        """

        if not tools:
            return self.call(
                messages=messages,
                temperature=temperature,
            )

        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
        ).choices[0].message

    # ==============================================================
    # SAFE CONTENT EXTRACTION
    # ==============================================================

    @staticmethod
    def get_content(message) -> str:
        """
        Safely extract text from a Groq/OpenAI-compatible message.
        """

        if message is None:
            return ""

        content = getattr(
            message,
            "content",
            None,
        )

        # Normal response
        if isinstance(content, str):
            return content.strip()

        # No content
        if content is None:
            return ""

        # Structured content
        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, dict):

                    text = item.get("text")

                    if isinstance(text, str):
                        parts.append(text)

                else:

                    text = getattr(
                        item,
                        "text",
                        None,
                    )

                    if isinstance(text, str):
                        parts.append(text)

            return "\n".join(parts).strip()

        return str(content).strip()

    # ==============================================================
    # TOOL CALL EXTRACTION
    # ==============================================================

    @staticmethod
    def get_tool_calls(message) -> list:
        """
        Safely extract tool calls.
        """

        if message is None:
            return []

        return list(
            getattr(
                message,
                "tool_calls",
                None,
            )
            or []
        )

    # ==============================================================
    # JSON / QUERY REWRITING CALL
    # ==============================================================

    def call_json_schema(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> dict:
        """
        Force the model to return a JSON object.

        Used by query rewriting.
        """

        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                "type": "json_object"
            },
            temperature=0.0,
        )

        message = response.choices[0].message

        content = self.get_content(
            message
        )

        if not content:
            raise ValueError(
                "LLM returned an empty JSON response."
            )

        try:

            return json.loads(content)

        except json.JSONDecodeError as exc:

            logger.exception(
                "LLM returned invalid JSON: %s",
                content,
            )

            raise ValueError(
                "LLM returned invalid JSON."
            ) from exc


# ==============================================================
# SINGLE SHARED CLIENT
# ==============================================================

llm_client = LLMClient()