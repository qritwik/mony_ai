import openai
import json


class OpenAIClient:
    def __init__(self, api_key):
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
        """
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add user message
        messages.append({"role": "user", "content": user_message})

        # Add assistant message if provided (for context/conversation)
        if assistant_message:
            messages.append({"role": "assistant", "content": assistant_message})

        # Response format
        response_format = {"type": "json_object"} if structured_output else None

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=response_format,
        )

        content = response.choices[0].message.content

        # If structured output, parse JSON before returning
        if structured_output:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON returned: {content}")

        return content
