import openai
import json


class OpenAIClient:
    def __init__(self, api_key):
        # Each thread/process can create its own client safely
        self.client = openai.OpenAI(api_key=api_key)

    def chat(
        self,
        user_message,
        system_message=None,
        assistant_message=None,
        model="gpt-4o-mini",
        structured_output=False,
    ):
        """
        Send chat message to OpenAI and get response.
        If structured_output=True, returns valid JSON.
        Thread-safe: each thread has its own client instance.
        """
        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": user_message})

        if assistant_message:
            messages.append({"role": "assistant", "content": assistant_message})

        response_format = {"type": "json_object"} if structured_output else None

        # No lock needed, because this instance is not shared
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=response_format,
        )

        content = response.choices[0].message.content

        if structured_output:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON returned: {content}")

        return content
