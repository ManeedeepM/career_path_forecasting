from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pickle
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = "career_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load ML model files
model = pickle.load(open(os.path.join(BASE_DIR, "model.pkl"), "rb"))
scaler = pickle.load(open(os.path.join(BASE_DIR, "scaler.pkl"), "rb"))
columns = pickle.load(open(os.path.join(BASE_DIR, "columns.pkl"), "rb"))

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS predictions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            result TEXT,
            probability INTEGER,
            date TEXT
        )
        """)
        db.commit()

init_db()

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")

# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"].lower()
        password = generate_password_hash(request.form["password"])

        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if existing:
            return render_template("register.html", error="Email already exists")

        db.execute("INSERT INTO users (username,email,password) VALUES (?,?,?)",
                   (username, email, password))
        db.commit()
        return redirect("/")

    return render_template("register.html")

# ================= FORGOT PASSWORD =================
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"].lower()
        new_password = generate_password_hash(request.form["password"])

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user:
            db.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
            db.commit()
            return redirect("/")
        else:
            return render_template("forgot.html", error="Email not registered")

    return render_template("forgot.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html")

# ================= PREDICTION =================
@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        target_role = request.form["target_role"]

        rank = float(request.form["rank"])
        gpa = float(request.form["gpa"])
        internships = int(request.form["internships"])
        projects = int(request.form["projects"])
        skills = int(request.form["skills"])
        offers = int(request.form["offers"])

        input_data = pd.DataFrame(0, index=[0], columns=columns)

        input_data["University_Ranking"] = rank
        input_data["Updated_University_GPA"] = gpa
        input_data["Internships_Completed"] = internships
        input_data["Projects_Completed"] = projects
        input_data["Soft_Skills_Score"] = skills
        input_data["Job_Offers"] = offers

        num_cols = [
            "University_Ranking",
            "Updated_University_GPA",
            "Internships_Completed",
            "Projects_Completed",
            "Soft_Skills_Score",
            "Job_Offers"
        ]

        input_data[num_cols] = scaler.transform(input_data[num_cols])

        prediction = model.predict(input_data)[0]
        prob = int(model.predict_proba(input_data)[0][1] * 100)

        result_text = "High Probability 🎉" if prediction == 1 else "Needs Improvement 📘"

        skill_gaps = []
        if gpa < 7: skill_gaps.append("Improve GPA")
        if internships < 2: skill_gaps.append("Gain more internships")
        if projects < 3: skill_gaps.append("Build more projects")

        role_suggestions = {
            "Software Engineer": ["Master DSA", "Build Full Stack Projects"],
            "Data Scientist": ["Learn Machine Learning", "Work on real datasets"],
            "AI Engineer": ["Deep Learning", "TensorFlow / PyTorch"],
            "Cyber Security Analyst": ["Networking", "Ethical Hacking"]
        }

        jobs = {
            "Software Engineer": [
                {"title": "Backend Developer", "company": "Infosys", "location": "Bangalore", "salary": "6-10 LPA"}
            ],
            "Data Scientist": [
                {"title": "ML Engineer", "company": "Wipro", "location": "Chennai", "salary": "8-12 LPA"}
            ]
        }

        db = get_db()
        db.execute(
            "INSERT INTO predictions (user_id,result,probability,date) VALUES (?,?,?,?)",
            (session["user_id"], result_text, prob,
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        db.commit()

        return render_template("result.html",
                               prediction_text=result_text,
                               probability=prob,
                               skill_gaps=skill_gaps,
                               recommendations=role_suggestions.get(target_role, []),
                               jobs=jobs.get(target_role, []),
                               target_role=target_role)

    return render_template("predict.html")

# ================= HISTORY =================
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    records = db.execute(
        "SELECT id,result,probability,date FROM predictions WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    return render_template("history.html", records=records)

# ================= DELETE =================
@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    db.execute("DELETE FROM predictions WHERE id=? AND user_id=?",
               (id, session["user_id"]))
    db.commit()
    return redirect("/history")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)