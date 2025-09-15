import requests
import time
import json


class TelegramClient:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_update_id = 0
        self.last_request_time = 0

    def _rate_limit(self):
        """Prevent rate limiting"""
        current_time = time.time()
        if current_time - self.last_request_time < 0.1:
            time.sleep(0.1)
        self.last_request_time = time.time()

    def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self._rate_limit()
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text}

        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Send message error: {response.text}")
                return None
        except Exception as e:
            print(f"Send message exception: {e}")
            return None

    def get_updates(self, offset=None, timeout=2):
        self._rate_limit()
        url = f"{self.base_url}/getUpdates"
        data = {"timeout": timeout, "limit": 100}
        if offset:
            data["offset"] = offset

        try:
            response = requests.post(url, data=data, timeout=timeout + 5)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return result
                else:
                    print(f"API Error: {result}")
                    return None
            else:
                print(f"HTTP Error {response.status_code}: {response.text}")
                return None

        except requests.exceptions.Timeout:
            return None
        except Exception as e:
            print(f"Get updates error: {e}")
            return None

    def create_reply_keyboard_with_custom(self, options, buttons_per_row=2):
        """Create keyboard with predefined options + custom input capability"""
        keyboard = []
        current_row = []

        # Add predefined options
        for i, option in enumerate(options):
            current_row.append(option)
            if len(current_row) == buttons_per_row or i == len(options) - 1:
                keyboard.append(current_row)
                current_row = []

        # Add custom input option
        keyboard.append(["✏️ Type my own answer"])

        return {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": False,  # Keep keyboard visible for custom typing
        }

    def remove_reply_keyboard(self):
        return {"remove_keyboard": True}

    def wait_for_selection_or_custom_input(
        self,
        chat_id,
        message,
        predefined_options,
        parse_mode=None,
        timeout_minutes=5,
        buttons_per_row=2,
    ):
        """
        Handle both reply button selections AND custom text input
        Returns: {"type": "predefined"|"custom", "value": selected_text}
        """
        # Create keyboard with predefined options + custom option
        keyboard = self.create_reply_keyboard_with_custom(
            predefined_options, buttons_per_row
        )

        prompt_text = f"{message}\n\nChoose from buttons below OR type your own answer:"
        sent = self.send_message(
            chat_id, prompt_text, parse_mode=parse_mode, reply_markup=keyboard
        )
        if not sent:
            return None

        # Initialize offset
        if self.last_update_id == 0:
            updates = self.get_updates(timeout=1)
            if updates and updates.get("result"):
                for update in updates["result"]:
                    self.last_update_id = max(
                        self.last_update_id, update["update_id"] + 1
                    )

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        custom_input_mode = False

        while time.time() - start_time < timeout_seconds:
            try:
                updates = self.get_updates(offset=self.last_update_id, timeout=2)

                if not updates:
                    continue

                results = updates.get("result", [])
                if not results:
                    continue

                for update in results:
                    # Update offset immediately
                    self.last_update_id = update["update_id"] + 1

                    if "message" not in update:
                        continue

                    msg = update["message"]

                    if str(msg["chat"]["id"]) != str(chat_id):
                        continue

                    if "text" not in msg:
                        continue

                    user_text = msg["text"].strip()
                    print(f"Received: '{user_text}'")

                    # Check if user selected "Type my own answer"
                    if user_text == "✏️ Type my own answer":
                        custom_input_mode = True
                        self.send_message(
                            chat_id,
                            "✏️ Please type your custom answer:",
                            reply_markup=self.remove_reply_keyboard(),
                        )
                        continue

                    # If in custom input mode, accept any text
                    if custom_input_mode:
                        self.send_message(
                            chat_id, f"✅ Got your custom answer: {user_text}"
                        )
                        return {"type": "custom", "value": user_text}

                    # Check if text matches predefined options (button selection)
                    elif user_text in predefined_options:
                        self.send_message(
                            chat_id,
                            f"✅ You selected: {user_text}",
                            reply_markup=self.remove_reply_keyboard(),
                        )
                        return {"type": "predefined", "value": user_text}

                    # User typed something directly (not a button, treat as custom)
                    else:
                        self.send_message(
                            chat_id,
                            f"✅ Got your custom input: {user_text}",
                            reply_markup=self.remove_reply_keyboard(),
                        )
                        return {"type": "custom", "value": user_text}

            except Exception as e:
                print(f"Error in polling loop: {e}")
                time.sleep(1)

        # Timeout
        self.send_message(
            chat_id, "⏰ Selection timeout.", reply_markup=self.remove_reply_keyboard()
        )
        return None

    def wait_for_user_input(self, chat_id, timeout_minutes=5, prompt_message=None):
        """Wait for any text input from user (no buttons)"""
        if prompt_message:
            self.send_message(
                chat_id, prompt_message, reply_markup=self.remove_reply_keyboard()
            )

        if self.last_update_id == 0:
            updates = self.get_updates(timeout=1)
            if updates and updates.get("result"):
                for update in updates["result"]:
                    self.last_update_id = max(
                        self.last_update_id, update["update_id"] + 1
                    )

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        while time.time() - start_time < timeout_seconds:
            try:
                updates = self.get_updates(offset=self.last_update_id, timeout=2)

                if not updates:
                    continue

                results = updates.get("result", [])
                if not results:
                    continue

                for update in results:
                    self.last_update_id = update["update_id"] + 1

                    if "message" not in update:
                        continue

                    msg = update["message"]

                    if str(msg["chat"]["id"]) != str(chat_id):
                        continue

                    if "text" not in msg:
                        continue

                    return msg["text"].strip()

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

        return None
