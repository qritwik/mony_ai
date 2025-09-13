import os
from client.gmail_client import GmailClient
from client.openai_client import OpenAIClient
from client.telegram_client import TelegramClient
from client.postgres_client import PostgresClient
from datetime import datetime
from dateutil import parser
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


def check_finance_email(gmail_data):
    openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))

    system_message = """
    You are an expert at parsing HTML email content.  

    Your task is to:  
    1. Determine whether the email is a **finance related transaction alert** (debit or credit) from a valid source such as a bank or UPI. Ignore promotional or marketing emails.  
    2. If the email is finance related, extract the following fields:  
    
       - Transaction Type (string: "debit" or "credit")  
       - Amount (string, numeric value only, e.g., "1500.00")  
       - Counterparty (string — "paid to whom" if debit, "received from whom" if credit)  
       - Transaction ID (string)  
       - Transaction Date (string in YYYY-MM-DD format, IST timezone)  
       - Transaction Time (string in HH:MM:SS format, IST 24-hour clock)  
    
    3. Use the **Email Received Time** for `transaction_date` and `transaction_time` if not explicitly available in the email body.  
    4. If any field is missing or unclear, return it as an empty string `""`.  
    5. The final output must always include a top-level field:  
    
       - `"is_finance_email"`: `true` or `false`  
    
    If `"is_finance_email": false`, no transaction fields are required.  
    If `"is_finance_email": true`, return the fields in a structured JSON.
    """

    user_message = f"""
    Email Subject: {gmail_data["subject"]}
    Email Received Time: {gmail_data["date"]}
    HTML Content from Email: {gmail_data["html_body"]}
    """

    assistant_message = """
    Use the sample json for response:

    If finance related:
    {
      "is_finance_email": true,
      "transaction_type": "debit",
      "amount": "1500.00",
      "counterparty": "Amazon",
      "transaction_id": "TXN123456789",
      "transaction_date": "2025-09-13",
      "transaction_time": "14:35:20"
    }
    
    If not finance related:
    {
      "is_finance_email": false
    }
    """

    response = openai_client.chat(
        system_message=system_message,
        user_message=user_message,
        assistant_message=assistant_message,
        structured_output=True,
    )
    return response


def chat_summarizer(transaction_detail):
    def format_datetime(dt_str: str) -> str:
        # More flexible parsing
        dt = parser.parse(dt_str)
        return dt.strftime("%d %b %Y at %I:%M %p")

    formatted_datetime_str = format_datetime(
        f"{transaction_detail['transaction_date']} {transaction_detail['transaction_time']}"
    )
    return (
        f"*Transaction Alert:*\n"
        f"Paid ₹{transaction_detail['amount']} to {transaction_detail['counterparty']} "
        f"on {formatted_datetime_str}\n\n"
        f"_Transaction ID:_ *{transaction_detail['transaction_id']}*"
    )


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


def log_user_workflow_run(data):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    pg_client.insert_or_update(
        table="workflow_run",
        data=data,
        conflict_columns=["user_id", "email_message_id"],
    )

    pg_client.close()


def is_message_already_processed(user_id, message_id):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    query = """
        SELECT 1 
        FROM workflow_run
        WHERE user_id = %s
          AND email_message_id = %s
          AND run_status = 'success'
        LIMIT 1;
    """
    result = pg_client.execute_query(query, (user_id, message_id))
    print(result)
    return len(result) > 0


def run_workflow(user_id: int):
    run_start_time = datetime.now()
    run_status = "failure"
    error_message = ""

    try:
        # Step 1: Fetch latest Gmail
        user_query = "in:inbox newer_than:1d"
        email_data = read_gmail(query=user_query)

        # Step 2: Check if message already processed
        if is_message_already_processed(
            user_id=user_id, message_id=email_data["message_id"]
        ):
            print(
                f"Email {email_data['message_id']} already processed successfully. Skipping..."
            )
            run_status = "success"
            return (
                run_status,
                error_message,
                run_start_time,
                datetime.now(),
                email_data,
                {},
            )

        # Step 3: Classify finance email & extract details
        transaction_info = check_finance_email(gmail_data=email_data)
        print(f"Email subject: {email_data['subject']}")

        if not transaction_info["is_finance_email"]:
            print("Not a finance email")
            run_status = "success"
            return (
                run_status,
                error_message,
                run_start_time,
                datetime.now(),
                email_data,
                transaction_info,
            )

        # Step 4: Generate transaction summary
        telegram_message = chat_summarizer(transaction_detail=transaction_info)

        # Step 5: Send Telegram message & get category
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        category_selection = send_telegram_message(
            transaction_message=telegram_message,
            chat_id=telegram_chat_id,
        )
        transaction_category = (
            category_selection["value"] if category_selection else "Uncategorized"
        )

        # Step 6: Insert into user transactions table
        user_transaction = {
            "user_id": user_id,
            "transaction_type": transaction_info["transaction_type"],
            "amount": transaction_info["amount"],
            "counterparty": transaction_info["counterparty"],
            "transaction_id": transaction_info["transaction_id"],
            "transaction_date": transaction_info["transaction_date"],
            "transaction_time": transaction_info["transaction_time"],
            "transaction_category": transaction_category,
        }
        insert_user_transaction_to_db(data=user_transaction)

        run_status = "success"
        return (
            run_status,
            error_message,
            run_start_time,
            datetime.now(),
            email_data,
            transaction_info,
        )

    except Exception as e:
        run_status = "failure"
        error_message = str(e)
        return (
            run_status,
            error_message,
            run_start_time,
            datetime.now(),
            locals().get("email_data", {}),
            locals().get("transaction_info", {}),
        )


if __name__ == "__main__":
    user_id = 5
    (
        run_status,
        error_message,
        run_start_time,
        run_end_time,
        email_data,
        transaction_info,
    ) = run_workflow(user_id)

    # Always log workflow run
    log_user_workflow_run(
        data={
            "user_id": user_id,
            "run_start_datetime": run_start_time,
            "run_end_datetime": run_end_time,
            "email_message_id": email_data.get("message_id", ""),
            "email_subject": email_data.get("subject", ""),
            "is_finance_email": transaction_info.get("is_finance_email", False),
            "run_status": run_status,
            "error_message": error_message,
        }
    )

    if run_status == "success":
        print("Workflow ran successfully!")
    else:
        print(f"Workflow failed: {error_message}")
