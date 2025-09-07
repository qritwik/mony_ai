# Python Multi-Client Integration Library

A comprehensive Python library that provides easy-to-use client interfaces for Gmail, OpenAI, Telegram, and PostgreSQL integrations. This library simplifies common tasks like email management, AI interactions, messaging, and database operations.

## Features

- **Gmail Client**: Email retrieval, marking as read, advanced search capabilities
- **OpenAI Client**: Simple chat interface for AI interactions
- **Telegram Client**: Message sending with formatting and interactive button selections
- **PostgreSQL Client**: Singleton database connection with CRUD operations

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in your project root with the following variables:

```env
# Gmail API Credentials
GOOGLE_ACCESS_TOKEN=your_gmail_access_token
GOOGLE_REFRESH_TOKEN=your_gmail_refresh_token
GOOGLE_CLIENT_ID=your_gmail_client_id
GOOGLE_CLIENT_SECRET=your_gmail_client_secret

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# PostgreSQL Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

## Usage Examples

### Gmail Client

```python
from gmail_client import GmailClient
import os

# Initialize Gmail client
gmail = GmailClient(
    access_token=os.getenv("GOOGLE_ACCESS_TOKEN"),
    refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
)

# Get unread emails
unread = gmail.get_emails("is:unread", 5)
print(f"Found {len(unread)} unread emails")

# Mark email as read
if unread:
    gmail.mark_as_read(unread[0]['id'])
    
# Mark multiple emails as read
email_ids = [email['id'] for email in unread[:3]]
gmail.mark_multiple_as_read(email_ids)

# Advanced email searches
latest = gmail.get_emails("", 5)  # Latest 5 emails
inbox = gmail.get_emails("in:inbox", 5)  # 5 inbox emails
primary = gmail.get_emails("category:primary", 5)  # Primary category
important = gmail.get_emails("subject:important", 3)  # Subject filter
from_boss = gmail.get_emails("from:boss@company.com", 5)  # Sender filter
with_attachments = gmail.get_emails("has:attachment", 5)  # With attachments
recent = gmail.get_emails("newer_than:7d", 10)  # Last 7 days
combo = gmail.get_emails("is:unread in:inbox", 5)  # Combined filters
```

### OpenAI Client

```python
from openai_client import OpenAIClient
import os

# Initialize OpenAI client
openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))

# Simple chat interaction
response = openai_client.chat("Hello, how are you?")
print(response)
```

### Telegram Client

```python
from telegram_client import TelegramClient
import os

# Initialize Telegram client
telegram = TelegramClient(os.getenv("TELEGRAM_BOT_TOKEN"))
chat_id = os.getenv("TELEGRAM_CHAT_ID")

# Send simple message
result = telegram.send_message(
    chat_id=chat_id,
    text="Hello from Python!"
)

# Send HTML formatted message
result = telegram.send_message(
    chat_id=chat_id,
    text="<b>Bold text</b> and <i>italic text</i>",
    parse_mode="HTML"
)

# Send Markdown formatted message
result = telegram.send_message(
    chat_id=chat_id,
    text="*Bold text* and _italic text_",
    parse_mode="Markdown"
)

# Interactive button selection with custom input option
food_options = [
    "🍕 Pizza", "🍔 Burger", "🥗 Salad", "🍜 Ramen",
    "🍰 Cake", "🍦 Ice Cream", "🌮 Tacos", "🍣 Sushi"
]

result = telegram.wait_for_selection_or_custom_input(
    chat_id=chat_id,
    message="What's your favorite food?",
    predefined_options=food_options,
    timeout_minutes=1,
    buttons_per_row=4
)

if result:
    if result["type"] == "predefined":
        telegram.send_message(
            chat_id, 
            f"Great choice! {result['value']} is delicious! 😋"
        )
    elif result["type"] == "custom":
        telegram.send_message(
            chat_id,
            f"Interesting! I haven't heard of '{result['value']}' before."
        )
```

### PostgreSQL Client (Singleton Pattern)

```python
from postgres_client import PostgresClient
import os

# Method 1: Direct instantiation (singleton)
pg1 = PostgresClient(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", 5432),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

# Method 2: Another instance - same object (singleton behavior)
pg2 = PostgresClient()

# Method 3: Using class method
pg3 = PostgresClient.get_instance()

# All instances are the same object
print(f"All same instance: {pg1 is pg2 is pg3}")  # True

# Create table
pg1.execute_query("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(150) UNIQUE,
        age INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Insert data
pg1.insert_or_update(
    "users", 
    {"name": "Alice Johnson", "email": "alice@example.com", "age": 30}
)

# Query data
users = pg2.execute_query("SELECT * FROM users")
print("Users:", users)

# Update data
pg3.insert_or_update(
    "users",
    {"name": "Alice Updated", "email": "alice@example.com", "age": 31},
    update_column="email"
)

# Parameterized query
user = pg1.execute_query(
    "SELECT * FROM users WHERE email = %s", 
    ("alice@example.com",)
)

# Close connection
pg1.close()
```

## API Reference

### Gmail Client Methods

- `get_emails(query, max_results)` - Retrieve emails based on Gmail search query
- `mark_as_read(email_id)` - Mark single email as read
- `mark_multiple_as_read(email_ids)` - Mark multiple emails as read

### OpenAI Client Methods

- `chat(message)` - Send message to OpenAI and get response

### Telegram Client Methods

- `send_message(chat_id, text, parse_mode)` - Send formatted message
- `wait_for_selection_or_custom_input()` - Interactive button selection with timeout

### PostgreSQL Client Methods

- `execute_query(query, params)` - Execute SQL query with optional parameters
- `insert_or_update(table, data, update_column)` - Insert or update record
- `get_instance()` - Get singleton instance
- `close()` - Close database connection

## Gmail Search Query Examples

| Query | Description |
|-------|-------------|
| `is:unread` | Unread emails |
| `in:inbox` | Inbox emails |
| `category:primary` | Primary category emails |
| `subject:important` | Subject contains "important" |
| `from:user@domain.com` | From specific sender |
| `has:attachment` | Emails with attachments |
| `newer_than:7d` | Last 7 days |
| `is:unread in:inbox` | Unread emails in inbox |

## Error Handling

All clients include basic error handling. Wrap client operations in try-catch blocks for production use:

```python
try:
    emails = gmail.get_emails("is:unread", 5)
except Exception as e:
    print(f"Gmail error: {e}")

try:
    response = openai_client.chat("Hello")
except Exception as e:
    print(f"OpenAI error: {e}")

try:
    result = telegram.send_message(chat_id, "Hello")
except Exception as e:
    print(f"Telegram error: {e}")

try:
    users = pg.execute_query("SELECT * FROM users")
except Exception as e:
    print(f"Database error: {e}")
```

## Dependencies

- `google-api-python-client` - Gmail API
- `openai` - OpenAI API
- `python-telegram-bot` - Telegram Bot API
- `psycopg2-binary` - PostgreSQL adapter
- `python-dotenv` - Environment variables

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions, please open an issue on the GitHub repository.