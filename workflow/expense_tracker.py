import os
import json
from workflow.client.gmail_client import GmailClient
from workflow.client.openai_client import OpenAIClient
from workflow.client.telegram_client import TelegramClient
from workflow.client.postgres_client import PostgresClient
from datetime import datetime, timedelta
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

    unread = gmail.get_emails(query, 1)
    if not unread:
        return None  # or {}

    email = unread[0]
    return {
        "message_id": email.get("id", ""),
        "subject": email.get("subject", ""),
        "date": email.get("date", ""),
        "html_body": email.get("html_body", ""),
    }


def get_user_last_email_epoch(user_id):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    query = """
        SELECT MAX(run_start_datetime) as last_run
        FROM workflow_run
        WHERE user_id = %s;
    """

    result = pg_client.execute_query(query, (user_id,))
    last_run_datetime = (
        result[0]["last_run"] if result and result[0]["last_run"] else None
    )

    if last_run_datetime:
        # Convert datetime to epoch (int)
        return int(last_run_datetime.timestamp())
    else:
        # Default: now - 10 hours
        fallback_time = datetime.now() - timedelta(hours=10)
        return int(fallback_time.timestamp())


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


def get_user_transaction_categories(user_id):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    query = """
        SELECT distinct category
        FROM transaction_category
        WHERE user_id = %s
          AND is_active = %s;
    """
    result = pg_client.execute_query(
        query,
        (
            user_id,
            True,
        ),
    )

    return [row["category"] for row in result]


def get_user_telegram_info(user_id):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    query = """
        SELECT telegram_chat_id
        FROM user_telegram
        WHERE user_id = %s;
    """
    result = pg_client.execute_query(
        query,
        (user_id,),
    )

    if len(result) > 0:
        return result[0]["telegram_chat_id"]
    else:
        return None


def send_telegram_message(transaction_message, transaction_categories, chat_id):
    telegram = TelegramClient(os.getenv("TELEGRAM_BOT_TOKEN"))

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

    try:
        pk = pg_client.insert_or_update(
            table="user_transactions",
            data=data,
            conflict_columns=["user_id", "transaction_id"],
            pk_column="id",
        )

        if not pk:
            raise ValueError("Failed to insert or update user transaction")

        return pk

    finally:
        pg_client.close()


def log_user_workflow_run(data):
    pg_client = PostgresClient(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    # Add/overwrite updated_at before insert
    data["updated_at"] = datetime.now()

    pg_client.insert_or_update(
        table="workflow_run",
        data=data,
        conflict_columns=["user_id", "email_message_id"],
        pk_column="run_id",
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
    return len(result) > 0


def identify_category_using_llm(transaction_detail, user_transaction_categories):
    openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))

    system_message = """
    You are a financial assistant that classifies transactions into predefined categories. 
    Always choose the MOST relevant category from the provided list. 
    If nothing fits, return "Others".
    """

    user_message = f"""
    Transaction Detail:
    {json.dumps(transaction_detail, indent=2)}

    Available Categories:
    {user_transaction_categories}
    """

    assistant_message = """
    Respond with only a JSON object in the format:
    {
      "category": "<best matching category>"
    }
    """

    response = openai_client.chat(
        system_message=system_message,
        user_message=user_message,
        assistant_message=assistant_message,
        structured_output=True,
    )

    # Defensive parsing
    try:
        category = response.get("category", "Others")
    except Exception:
        category = "Others"

    return category


def identify_transaction_category(user_id, transaction_detail):
    # Get all transaction categories for user
    user_transaction_categories = get_user_transaction_categories(user_id=user_id)

    # Check if user telegram is connected
    telegram_chat_id = get_user_telegram_info(user_id=user_id)

    if telegram_chat_id:
        telegram_message = chat_summarizer(transaction_detail=transaction_detail)
        category_selection = send_telegram_message(
            transaction_message=telegram_message,
            transaction_categories=user_transaction_categories,
            chat_id=telegram_chat_id,
        )
        if category_selection:
            print("Received category from user's telegram!")
            transaction_category = category_selection["value"]
        else:
            print("Not received category from user's telegram!")
            transaction_category = identify_category_using_llm(
                transaction_detail, user_transaction_categories
            )
    else:
        print("User Telegram not Connected!")
        transaction_category = identify_category_using_llm(
            transaction_detail, user_transaction_categories
        )

    print(f"Transaction category is: {transaction_category}")
    return transaction_category


def run_workflow(user_id: int):
    run_start_time = datetime.now()
    run_status = "failure"
    error_message = ""

    try:
        # Step 1: Fetch latest Gmail
        user_last_read_epoch = get_user_last_email_epoch(user_id=user_id)

        # Used for testing
        # user_query = f"in:inbox category:primary from:alerts@hdfcbank.net"

        user_query = f"in:inbox category:primary after:{user_last_read_epoch}"
        email_data = read_gmail(query=user_query)
        if not email_data:
            print("No unread emails found.")
            return "success", "", run_start_time, datetime.now(), {}, {}

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

        # Step 4: Identify transaction category
        transaction_category = identify_transaction_category(
            user_id=user_id, transaction_detail=transaction_info
        )

        # Step 5: Insert into user transactions table
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
        transaction_pk = insert_user_transaction_to_db(data=user_transaction)
        transaction_info["transaction_pk"] = transaction_pk

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
    user_id = 10
    (
        run_status,
        error_message,
        run_start_time,
        run_end_time,
        email_data,
        transaction_info,
    ) = run_workflow(user_id)

    # Only log if email data is not empty
    if email_data:
        log_user_workflow_run(
            data={
                "user_id": user_id,
                "user_transaction_id": transaction_info.get("transaction_pk"),
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
