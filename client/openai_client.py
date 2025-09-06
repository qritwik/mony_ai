import openai


class OpenAIClient:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)

    def chat(
        self,
        user_message,
        system_message=None,
        assistant_message=None,
        model="gpt-4o-mini",
    ):
        """Send chat message to OpenAI and get response"""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add user message
        messages.append({"role": "user", "content": user_message})

        # Add assistant message if provided (for context/conversation)
        if assistant_message:
            messages.append({"role": "assistant", "content": assistant_message})

        # Call OpenAI API
        response = self.client.chat.completions.create(model=model, messages=messages)

        return response.choices[0].message.content
