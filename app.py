import os
from dotenv import load_dotenv

load_dotenv()
from client.gmail_client import GmailClient
from client.openai_client import OpenAIClient
from client.telegram_client import TelegramClient


# Usage examples:
if __name__ == "__main__":
    # gmail = GmailClient(
    #     access_token=os.getenv("GOOGLE_ACCESS_TOKEN"),
    #     refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
    #     client_id=os.getenv("GOOGLE_CLIENT_ID"),
    #     client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    # )
    #
    # # Get emails (now includes 'id' field)
    # unread = gmail.get_emails("is:unread", 1)
    # print(f"Found {len(unread)} unread emails")
    #
    # print(unread)

    # # Mark single email as read
    # if unread:
    #     gmail.mark_as_read(unread[0]['id'])
    #     print(f"Marked email '{unread[0]['subject']}' as read")
    #
    # # Mark multiple emails as read
    # if len(unread) > 1:
    #     email_ids = [email['id'] for email in unread[:3]]  # First 3 emails
    #     gmail.mark_multiple_as_read(email_ids)
    #     print(f"Marked {len(email_ids)} emails as read")
    #
    # # Custom searches
    # emails = gmail.get_emails("", 5)  # Latest 5 emails
    # unread = gmail.get_emails("is:unread", 10)  # 10 unread emails
    # inbox = gmail.get_emails("in:inbox", 5)  # 5 inbox emails
    # primary = gmail.get_emails("category:primary", 5)  # 5 primary emails
    # important = gmail.get_emails("subject:important", 3)  # Subject contains "important"
    # work = gmail.get_emails("from:boss@company.com", 5)  # From specific sender
    # attachments = gmail.get_emails("has:attachment", 5)  # With attachments
    # recent = gmail.get_emails("newer_than:7d", 10)  # Last 7 days
    # combo = gmail.get_emails("is:unread in:inbox", 5)  # Unread in inbox

    # Initialize client
    # openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))
    #
    # # Simple usage
    # response = openai_client.chat("Hello, how are you?")
    # print(response)

    telegram = TelegramClient(os.getenv("TELEGRAM_BOT_TOKEN"))
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # Send simple message
    # result = telegram.send_message(
    #     chat_id=os.getenv("TELEGRAM_CHAT_ID"), text="Hello from Python!"
    # )
    # print(result)
    #
    # # Send message with HTML formatting
    # result = telegram.send_message(
    #     chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    #     text="<b>Bold text</b> and <i>italic text</i>",
    #     parse_mode="HTML",
    # )
    # print(result)
    #
    # # Send message with Markdown formatting
    # result = telegram.send_message(
    #     chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    #     text="*Bold text* and _italic text_",
    #     parse_mode="Markdown",
    # )
    # print(result)

    # Example 1: Food preferences with custom option
    food_options = [
        "🍕 Pizza",
        "🍔 Burger",
        "🥗 Salad",
        "🍜 Ramen",
        "🍰 Cake",
        "🍦 Ice Cream",
        "🌮 Tacos",
        "🍣 Sushi",
    ]

    result = telegram.wait_for_selection_or_custom_input(
        chat_id=chat_id,
        message="What's your favorite food?",
        predefined_options=food_options,
        timeout_minutes=1,
        buttons_per_row=4,
    )

    print(result)

    # if result:
    #     if result["type"] == "predefined":
    #         telegram.send_message(
    #             chat_id, f"Great choice! {result['value']} is delicious! 😋"
    #         )
    #     elif result["type"] == "custom":
    #         telegram.send_message(
    #             chat_id,
    #             f"Interesting! I haven't heard of '{result['value']}' before. Tell me more about it!",
    #         )
    #
    #     print(f"User response: {result}")
    # else:
    #     print("No response or timeout")
