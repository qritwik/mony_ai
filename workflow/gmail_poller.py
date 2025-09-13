from celery import Celery, chain, group

# ------------------------------
# Celery App
# ------------------------------
app = Celery(
    "gmail_poller",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["gmail_poller"],  # ensures tasks in this file are registered
)


# ------------------------------
# Tasks
# ------------------------------
@app.task
def read_gmail(account_email):
    print(f"[{account_email}] Reading Gmail...")
    return {"emails": [f"{account_email}_mail1", f"{account_email}_mail2"]}


@app.task
def transform_data(data):
    print(f"Transforming data: {data}")
    return [mail.upper() for mail in data["emails"]]


@app.task
def send_message(transformed):
    print(f"Sending message: {transformed}")
    return f"Sent {len(transformed)} messages"


@app.task
def unread_email(status):
    print(f"Marking emails as unread: {status}")
    return f"All emails marked unread after: {status}"


@app.task
def custom_task(data):
    print(f"Custom processing: {data}")
    return f"Custom({data})"


# ------------------------------
# Chain factory
# ------------------------------
def create_chain(account_email):
    """
    Returns a chain of tasks. All chains have the same tasks,
    but arguments can differ per chain.
    """
    return chain(
        read_gmail.s(account_email),
        transform_data.s(),
        send_message.s(),
        unread_email.s(),
    )


# ------------------------------
# Run all chains in parallel
# ------------------------------
@app.task
def run_all_chains():
    """
    Runs multiple chains in parallel using a group.
    """
    accounts = ["user1@gmail.com"]
    all_chains = group(create_chain(email) for email in accounts)
    return all_chains.apply_async()


# ------------------------------
# Beat schedule
# ------------------------------
app.conf.beat_schedule = {
    "run-gmail-chains-every-minute": {
        "task": "gmail_poller.run_all_chains",
        "schedule": 30.0,  # every 1 minute
    }
}
app.conf.timezone = "UTC"

# ------------------------------
# Optional: quick test without celery
# ------------------------------
if __name__ == "__main__":
    run_all_chains.apply()
