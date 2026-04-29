from flask import Flask, jsonify, request, render_template
from database import get_db, init_db
import random

# --- Flaskアプリケーションのセットアップ ---
# 
app = Flask(__name__)

# --- appインスタンスにルートを登録 ---
@app.route("/")
def index():
    return render_template("index.html") # index.htmlは、ユーザーが日本語の単語を見て英語を入力するシンプルなUIを提供するテンプレートファイル

# APIエンドポイント：ランダムに1問出題する
@app.route("/api/question")
def get_question():
    conn = get_db()
    # ランダムに1問取得
    row = conn.execute(
        "SELECT id, japanese FROM words ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    return jsonify({"id": row["id"], "japanese": row["japanese"]})

# APIエンドポイント：ユーザーの解答をチェックする
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

# 単独実行でデータベースを初期化（データ登録)して、Flaskアプリを起動
if __name__ == "__main__":
    init_db()
    app.run(debug=True)  # デバッグモードで起動（コードを変更したら自動で再起動,エラーをブラウザに表示）
