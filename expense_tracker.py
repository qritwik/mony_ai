import os
from client.gmail_client import GmailClient
from client.openai_client import OpenAIClient
from client.telegram_client import TelegramClient
from dotenv import load_dotenv

load_dotenv()


def read_gmail(query):
    gmail = GmailClient(
        access_token=os.getenv("GOOGLE_ACCESS_TOKEN"),
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )

    # Get emails (now includes 'id' field)
    unread = gmail.get_emails(query, 1)

    subject = unread[0]["subject"]
    date = unread[0]["date"]
    html_body = unread[0]["html_body"]

    return {"subject": subject, "date": date, "html_body": html_body}


def llm_extract_fields(gmail_data):
    # Initialize OpenAI client
    openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))

    system_message = f"""
    You are an expert at parsing HTML email content. The email is a transaction alert from a bank, containing details of a payment.
    Your task is to extract the following key fields from the HTML:
    
    Transaction Type (string, "debit" or "credit")
    
    Amount (string, numeric value only, e.g., "1500.00")
    
    Counterparty (string — represents paid_to if debit, or received_from if credit)
    
    Transaction ID (string)
    
    Transaction Date (string in YYYY-MM-DD format)
    
    Transaction Time (string in HH:MM:SS format, 24-hour clock)
    
    Return the extracted information in a structured JSON.
    
    Use Email Received Time to extract transaction_date and transaction_time.
    Always show in IST 24 Hour format.
    
    If any field is missing or unclear, return it as an empty string "".
    """

    user_message = f"""
    Email Subject: {gmail_data["subject"]}
    Email Received Time: {gmail_data["date"]}
    HTML Content from Email: {gmail_data["html_body"]}
    """

    assistant_message = """
    Use the sample json for response:
    
    {
      "transaction_type": "",
      "amount": "",
      "counterparty": "",
      "transaction_id": "",
      "transaction_date": "",
      "transaction_time": ""
    }
    """

    # Simple usage
    response = openai_client.chat(
        system_message=system_message,
        user_message=user_message,
        assistant_message=assistant_message,
        structured_output=True,
    )
    return response


def llm_chat_summarizer(transaction_detail):
    # Initialize OpenAI client
    openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))

    system_message = f"""
    You are a message summarizer for an expense tracker bot. The account belongs to Ritwik Raj.

    If the transaction is debit, it means Ritwik paid the counterparty.
    
    If the transaction is credit, it means Ritwik received money from the counterparty.
    
    Your task is to generate a minimal, crisp text message (suitable for a Telegram bot) that includes:
    
    Who the transaction is with (counterparty).
    
    Whether Ritwik paid or received.
    
    Transaction amount.
    
    Transaction date and time. (Should always in IST format)
    
    At the bottom, include the Transaction ID in a smaller style (or simply as a plain line).
    
    The output must be only the text message, with no extra explanation.
    
    Time should be in IST 12 Hour Format.
    """

    user_message = f"""
    Here are the transaction details:
    
    Transaction ID: {transaction_detail['transaction_id']}
    Transaction Type: {transaction_detail['transaction_type']}
    Transaction Amount: {transaction_detail['amount']}
    Counterparty: {transaction_detail['counterparty']}
    Transaction Date: {transaction_detail['transaction_date']}
    Transaction Time: {transaction_detail['transaction_time']}
    """

    # Simple usage
    response = openai_client.chat(
        system_message=system_message, user_message=user_message
    )
    return response


def send_telegram_message(transaction_message):
    telegram = TelegramClient(os.getenv("TELEGRAM_BOT_TOKEN"))
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    bot_message = f"*Transaction Alert:*\n{transaction_message}"

    transaction_categories = [
        "🛍️ Shopping",
        "🍽️ Eating Out",
        "🍔 Online Food Order",
        "⚡ Quick Commerce",
        "🏪 Groceries",
        "☕ Cafe & Beverages",
        "🚕 Ride-Hailing / Taxi",
        "✈️ Travel & Flights",
        "🏨 Hotels & Stays",
        "🎬 Movies & Entertainment",
        "📱 Mobile Recharge & Bills",
        "💡 Utilities (Electricity, Water, Gas)",
        "🏥 Healthcare & Pharmacy",
        "🎁 Gifts & Lifestyle",
        "🛒 E-commerce",
        "👕 Fashion & Apparel",
        "🚗 Fuel & Transport",
        "📚 Education & Courses",
        "💳 Loan / EMI Payment",
        "🏦 Bank Transfers & Fees",
    ]

    result = telegram.wait_for_selection_or_custom_input(
        chat_id=chat_id,
        message=bot_message,
        predefined_options=transaction_categories,
        parse_mode="Markdown",
        timeout_minutes=1,
        buttons_per_row=3,
    )

    return result


if __name__ == "__main__":
    out1 = read_gmail(query="is:unread in:inbox newer_than:7d from:qritwik@gmail.com")
    out2 = llm_extract_fields(gmail_data=out1)
    out3 = llm_chat_summarizer(transaction_detail=out2)
    out4 = send_telegram_message(transaction_message=out3)
    print(out4)
