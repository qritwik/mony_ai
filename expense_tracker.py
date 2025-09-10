import os
from client.gmail_client import GmailClient
from client.openai_client import OpenAIClient
from client.telegram_client import TelegramClient
from client.postgres_client import PostgresClient
from datetime import datetime
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

    message_id = unread[0]["id"]
    subject = unread[0]["subject"]
    date = unread[0]["date"]
    html_body = unread[0]["html_body"]

    return {
        "message_id": message_id,
        "subject": subject,
        "date": date,
        "html_body": html_body,
    }


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


def chat_summarizer(transaction_detail):
    def format_datetime(dt_str: str) -> str:
        # Parse the given string into a datetime object
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

        # Format into the required style
        return dt.strftime("%d %b %Y at %I:%M %p")

    formatted_datetime_str = format_datetime(
        transaction_detail["transaction_date"]
        + " "
        + transaction_detail["transaction_time"]
    )
    chat_message = f"*Transaction Alert:*\nPaid ₹{transaction_detail['amount']} to {transaction_detail['counterparty']} on {formatted_datetime_str}\n\n_Transaction ID:_ *{transaction_detail['transaction_id']}*"
    return chat_message


def send_telegram_message(transaction_message, chat_id):
    telegram = TelegramClient(os.getenv("TELEGRAM_BOT_TOKEN"))

    # Todo: Create a transaction category table in postgres.
    # Todo: Fetch transaction category for the user from database.
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
        message=transaction_message,
        predefined_options=transaction_categories,
        parse_mode="Markdown",
        timeout_minutes=1,
        buttons_per_row=3,
    )

    return result


def insert_user_transaction_to_db(data):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    pg_client.insert_or_update(
        table="user_transactions",
        data=data,
        conflict_columns=["user_id", "transaction_id"],
    )

    pg_client.close()


def mark_email_read(message_id):
    gmail = GmailClient(
        access_token=os.getenv("GOOGLE_ACCESS_TOKEN"),
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )

    return gmail.mark_message_as_read(message_id=message_id)


if __name__ == "__main__":
    # Step-1
    user_query_str = "is:unread in:inbox newer_than:7d from:alerts@hdfcbank.net"
    out1 = read_gmail(query=user_query_str)

    # Step-2
    out2 = llm_extract_fields(gmail_data=out1)

    # Step-3
    out3 = chat_summarizer(transaction_detail=out2)

    # Step-4
    user_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    out4 = send_telegram_message(transaction_message=out3, chat_id=user_chat_id)

    # Step-5
    if out4:
        # User provided category
        if out4["type"] == "predefined":
            transaction_category = out4["value"]
        else:
            # custom category
            transaction_category = out4["value"]

            # Todo: 1. Use LLM to map custom category to our category
            # Todo: 2. If can't be mapped, create a new category for that user
    else:
        # User didn't provide category
        # Todo: Use LLM to fetch the category
        transaction_category = "Test"

    user_transaction_data = {
        "user_id": 1,
        "transaction_type": out2["transaction_type"],
        "amount": out2["amount"],
        "counterparty": out2["counterparty"],
        "transaction_id": out2["transaction_id"],
        "transaction_date": out2["transaction_date"],
        "transaction_time": out2["transaction_time"],
        "transaction_category": transaction_category,
    }

    insert_user_transaction_to_db(data=user_transaction_data)

    # Step-6
    out6 = mark_email_read(message_id=out1["message_id"])
    if out6:
        print("Workflow ran successfully!")
    else:
        print("Error while marking email as read!")
