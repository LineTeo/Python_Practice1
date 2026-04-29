from flask import Flask, jsonify, request, render_template
from database import get_db, init_db
import random

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/question")
def get_question():
    conn = get_db()
    # ランダムに1問取得
    row = conn.execute(
        "SELECT id, japanese FROM words ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    return jsonify({"id": row["id"], "japanese": row["japanese"]})

@app.route("/api/answer", methods=["POST"])
def check_answer():
    data = request.get_json()
    word_id = data["id"]
    user_answer = data["answer"].lower().strip()

    conn = get_db()
    row = conn.execute(
        "SELECT english FROM words WHERE id = ?", (word_id,)
    ).fetchone()
    conn.close()

    correct = row["english"]
    is_correct = user_answer == correct
    return jsonify({"correct": is_correct, "answer": correct})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
