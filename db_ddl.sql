CREATE TABLE IF NOT EXISTS users (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone BIGINT,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);


CREATE TABLE IF NOT EXISTS gmail_credentials (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    gmail_email TEXT UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS user_transactions (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    transaction_id TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    amount float NOT NULL,
    counterparty TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    transaction_time TEXT NOT NULL,
    transaction_category TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, transaction_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS transaction_category (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    category TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, category),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS workflow (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS workflow_run (
    run_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    user_transaction_id INT DEFAULT NULL,
    run_start_datetime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_end_datetime TIMESTAMP,
    email_message_id TEXT NOT NULL,
    email_subject TEXT,
    is_finance_email BOOLEAN NOT NULL DEFAULT FALSE,
    run_status TEXT NOT NULL CHECK (run_status IN ('success', 'failure')),
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, email_message_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (user_transaction_id) REFERENCES user_transactions (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS user_telegram (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    telegram_chat_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE (user_id),
    UNIQUE (telegram_chat_id)
);