import logging
from flask import (
    Flask,
    request,
    redirect,
    render_template,
    jsonify,
    session,
    flash,
    url_for,
)
from functools import wraps
from web_app.database_client import UserDB
from web_app.oauth_handler import GoogleOAuth
import pytz


app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Initialize components
db = UserDB()
oauth = GoogleOAuth()

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Use DEBUG for more details
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def login_required(f):
    """Decorator to require login for routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            logger.warning("Unauthorized access attempt to %s", request.path)
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def home():
    if "user_id" in session:
        username = session["username"]
        logger.info("User %s accessed home page", username)
        logger.info("Redirecting home '/' to dashboard")
        return redirect(url_for("dashboard"))
    logger.info("Redirecting unauthenticated user to login")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        logger.info("Login attempt for username: %s", username)

        if not username or not password:
            logger.warning("Login failed: Missing username or password")
            return render_template(
                "login.html", message="Please provide both username and password"
            )

        user = db.authenticate_user(username=username, password=password)

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["name"] = user["name"]
            logger.info("Login successful for username: %s", username)
            return redirect(url_for("dashboard"))
        else:
            logger.warning("Invalid login for username: %s", username)
            return render_template("login.html", message="Invalid username or password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        phone = request.form.get("phone")

        logger.info("Registration attempt for username: %s", username)

        # Validation
        if not all([name, username, password, confirm_password]):
            logger.warning("Registration failed: Missing fields")
            return render_template("register.html", message="All fields are required")

        if password != confirm_password:
            logger.warning("Registration failed: Passwords do not match")
            return render_template("register.html", message="Passwords do not match")

        if len(password) < 6:
            logger.warning("Registration failed: Weak password")
            return render_template(
                "register.html", message="Password must be at least 6 characters long"
            )

        if len(username) < 3:
            logger.warning("Registration failed: Short username")
            return render_template(
                "register.html", message="Username must be at least 3 characters long"
            )

        if phone and (len(phone) != 10 or not phone.isdigit()):
            logger.warning("Registration failed: Invalid phone number")
            return render_template(
                "register.html", message="Phone should be of 10 digits"
            )

        # Create user
        if db.create_user(name, username, password, phone):
            # Get the user_id for the user
            user_id = db.get_user_id(username=username)

            # Add default transaction category for the user
            db.add_default_transaction_categories(user_id=user_id)

            logger.info("User registered successfully: %s", username)
            return redirect(url_for("login"))
        else:
            logger.warning("Registration failed: Username already exists")
            return render_template("register.html", message="Username already exists")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    username = session.get("username")
    logger.info("User %s logged out", username)
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    # user info
    user_id = session.get("user_id")
    username = session.get("username")
    full_name = session.get("name")

    # workflow info
    user_gmail = db.get_user_gmail(user_id=user_id) or {}
    user_workflow = db.get_user_workflow(user_id=user_id) or {}
    user_data = {**user_gmail, **user_workflow}

    # Convert datetime to IST and format (assuming created_at is always datetime)
    if user_data.get("created_at"):
        utc_time = user_data["created_at"]

        # Make timezone-aware (UTC) if naive
        if utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=pytz.UTC)

        # Convert to IST and format
        ist_time = utc_time.astimezone(pytz.timezone("Asia/Kolkata"))
        user_data["created_at"] = ist_time.strftime("%B %d, %Y · %I:%M %p")

    # transaction info
    user_transaction_categories = db.get_transaction_categories(user_id=user_id)

    # telegram info
    telegram_data = db.get_telegram_info(user_id=user_id)

    logger.info("Dashboard accessed by user %s (ID: %s)", username, user_id)
    return render_template(
        "dashboard.html",
        username=username,
        full_name=full_name,
        user_data=user_data,
        user_transaction_categories=user_transaction_categories,
        telegram_data=telegram_data,
    )


@app.route("/auth")
@login_required
def auth():
    logger.info("OAuth authorization started for user %s", session.get("username"))
    return redirect(oauth.get_auth_url())


@app.route("/login/callback")
@login_required
def callback():
    """Handle OAuth callback and create workflow"""
    code = request.args.get("code")
    error = request.args.get("error")
    user_id = session["user_id"]

    if error:
        logger.error("Authorization error: %s", error)
        flash(f"Authorization error: {error}", "error")
        return redirect(url_for("dashboard"))

    if not code:
        logger.error("No authorization code received for user ID %s", user_id)
        flash("No authorization code received", "error")
        return redirect(url_for("dashboard"))

    try:
        logger.info("Processing OAuth callback for user ID %s", user_id)

        # Exchange code for tokens
        tokens = oauth.exchange_code(code)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        logger.info("Got OAuth tokens for user ID %s", user_id)

        # Get user gmail
        gmail = oauth.get_user_email(access_token)
        logger.info("Fetched Gmail %s for user ID %s", gmail, user_id)

        # Check if Gmail is already connected by another user
        gmail_credential = db.get_gmail_credential_by_email(gmail)
        if gmail_credential and gmail_credential["user_id"] != user_id:
            logger.warning("Gmail %s already connected by another user", gmail)
            flash(
                f"Gmail account {gmail} is already connected by another user", "error"
            )
            return redirect(url_for("dashboard"))

        # Save gmail credential to database
        db.create_gmail_credential(user_id, gmail, access_token, refresh_token)
        logger.info("Saved Gmail credential for user %s", gmail)

        # Create active workflow for user
        db.create_workflow(user_id=user_id)

        flash(
            f"Successfully connected Gmail account {gmail}!",
            "success",
        )
        return redirect(url_for("dashboard"))

    except Exception as e:
        logger.exception("OAuth setup failed for user ID %s", user_id)
        flash(f"Setup failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))


@app.route("/add_transaction_category", methods=["POST"])
@login_required
def add_transaction_category():
    user_id = session.get("user_id")
    transaction_category = request.form.get("transaction_category")

    if not all([transaction_category]):
        error_msg = "Missing transaction_category field!"
        logger.error(error_msg)
        flash(f"{error_msg}", "error")
        return redirect(url_for("dashboard"))

    db.create_transaction_category(user_id=user_id, category=transaction_category)

    return redirect(url_for("dashboard"))


@app.route("/delete_transaction_category", methods=["POST"])
@login_required
def delete_transaction_category():
    user_id = session.get("user_id")
    transaction_category = request.form.get("transaction_category")

    if not all([transaction_category]):
        error_msg = "Missing transaction_category field!"
        logger.error(error_msg)
        flash(f"{error_msg}", "error")
        return redirect(url_for("dashboard"))

    if db.delete_transaction_category(user_id=user_id, category=transaction_category):
        flash(f"Deleted transaction category : {transaction_category}")
        return redirect(url_for("dashboard"))
    else:
        flash(f"Error while deleting transaction category : {transaction_category}")
        return redirect(url_for("dashboard"))


@app.route("/disconnect_gmail_workflow", methods=["GET"])
@login_required
def disconnect_gmail_workflow():
    user_id = session.get("user_id")

    # Delete user expense tracker workflow
    db.delete_workflow(user_id=user_id)

    # Delete user gmail credentials
    db.delete_gmail_credential(user_id=user_id)

    flash(f"Gmail disconnected and workflow deactivated successfully!")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0", ssl_context="adhoc")
