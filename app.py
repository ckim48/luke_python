from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3, json, random
from datetime import date
from openai import OpenAI

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ---- Database connection ----
def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn
@app.route('/results')
def results():
    if "username" not in session:
        flash("Please log in to view your results.")
        return redirect(url_for("login"))

    conn = get_db_connection()
    history = conn.execute(
        "SELECT score, quiz_date FROM results WHERE username = ? ORDER BY quiz_date DESC",
        (session["username"],)
    ).fetchall()
    conn.close()

    return render_template("results.html", history=history)

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            quiz_date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


# ---- GPT Chatbot Endpoint ----
@app.route('/chat', methods=["POST"])
def chat():
    data = request.get_json()
    user_question = data.get("question")
    try:
        response = client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful CPR assistant. Answer clearly and use real resources when possible."},
                {"role": "user", "content": user_question}
            ]
        )
        return jsonify({"answer": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"answer": "Sorry, I couldn't respond right now."})

# ---- Quiz Logic ----
def get_daily_questions():
    with open("questions.json", "r") as file:
        all_questions = json.load(file)
    seed = int(date.today().strftime('%Y%m%d'))
    random.seed(seed)
    return random.sample(all_questions, 10)

@app.route('/')
def home():
    return render_template("index.html")
@app.route('/quiz', methods=["GET", "POST"])
def quiz():
    if "username" not in session:
        flash("Please log in to access the quiz.")
        return redirect(url_for("login"))

    questions = get_daily_questions()
    score = None
    results = {}

    if request.method == "POST":
        answers = json.loads(request.form.get("answers", "{}"))
        score = 0
        for q in questions:
            qid = str(q["id"])
            selected = answers.get(qid)
            correct = q["answer"]
            results[qid] = {
                "question": q["question"],
                "selected": selected,
                "correct": correct
            }
            if selected == correct:
                score += 1

        # Save result to DB
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO results (username, score, quiz_date) VALUES (?, ?, ?)",
            (session["username"], score, date.today().isoformat())
        )
        conn.commit()
        conn.close()

        # Show result page
        return render_template("result_page.html", score=score, results=results)

    return render_template("quiz.html", questions=questions)
@app.route('/profile')
def profile():
    if "username" not in session:
        flash("Please log in to view your profile.")
        return redirect(url_for("login"))

    conn = get_db_connection()
    history = conn.execute(
        "SELECT score, quiz_date FROM results WHERE username = ? ORDER BY quiz_date DESC",
        (session["username"],)
    ).fetchall()
    conn.close()

    return render_template("profile.html", username=session["username"], history=history)

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        existing_user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
            flash("Username already exists.")
        else:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Registration successful. Please log in.")
            conn.close()
            return redirect(url_for("login"))
        conn.close()
    return render_template("register.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        if user:
            session["username"] = user["username"]
            return redirect(url_for("quiz"))
        else:
            flash("Invalid credentials.")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop("username", None)
    flash("Logged out.")
    return redirect(url_for("login"))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
