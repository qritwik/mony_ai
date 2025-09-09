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
from server.database_client import UserDB
from server.oauth_handler import GoogleOAuth


app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Initialize components
db = UserDB()
oauth = GoogleOAuth()


def login_required(f):
    """Decorator to require login for routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def home():
    if "user_id" in session:
        username = session["username"]
        return render_template("dashboard.html", username=username)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template(
                "login.html", message="Please provide both username and password"
            )

        user = db.authenticate_user(username=username, password=password)

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
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

        # Validation
        if not all([name, username, password, confirm_password]):
            return render_template("register.html", message="All fields are required")

        if password != confirm_password:
            return render_template("register.html", message="Passwords do not match")

        if len(password) < 6:
            return render_template(
                "register.html", message="Password must be at least 6 characters long"
            )

        if len(username) < 3:
            return render_template(
                "register.html", message="Username must be at least 3 characters long"
            )

        if phone and len(phone) != 10 and not phone.isdigit():
            return render_template(
                "register.html", message="Phone should be of 10 digits"
            )

        # Create user
        if db.create_user(name, username, password, phone):
            return render_template("login.html")
        else:
            return render_template("register.html", message="Username already exists")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session.get("user_id")
    username = session.get("username")
    user_gmail = db.get_user_gmail(user_id=user_id)
    return render_template(
        "dashboard.html", user_id=user_id, username=username, user_gmail=user_gmail
    )


@app.route("/auth")
@login_required
def auth():
    return redirect(oauth.get_auth_url())


@app.route("/login/callback")
@login_required
def callback():
    """Handle OAuth callback and create workflow"""
    code = request.args.get("code")
    error = request.args.get("error")
    user_id = session["user_id"]

    if error:
        flash(f"Authorization error: {error}", "error")
        return redirect(url_for("dashboard"))

    if not code:
        flash("No authorization code received", "error")
        return redirect(url_for("dashboard"))

    try:
        print("🔄 Processing OAuth callback...")

        # Exchange code for tokens
        tokens = oauth.exchange_code(code)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        print("✅ Got OAuth tokens")

        # Get user gmail
        gmail = oauth.get_user_email(access_token)
        print(f"✅ Gmail: {gmail}")

        # Check if this Gmail account is already connected by another user
        gmail_credential = db.get_gmail_credential_by_email(gmail)
        if gmail_credential and gmail_credential["user_id"] != user_id:
            flash(
                f"Gmail account {gmail} is already connected by another user", "error"
            )
            return redirect(url_for("dashboard"))

        # Save credential to database
        db.create_gmail_credential(user_id, gmail, access_token, refresh_token)
        print("✅ Saved credential to database")

        flash(
            f"Successfully connected Gmail account {gmail}!",
            "success",
        )
        return redirect(url_for("dashboard"))

    except Exception as e:
        print(f"❌ Setup failed: {str(e)}")
        flash(f"Setup failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0", ssl_context="adhoc")
