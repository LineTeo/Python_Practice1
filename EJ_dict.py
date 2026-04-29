import tkinter as tk
from tkinter import messagebox

# 日本語と英語の単語を対応させた辞書
word = {
  "こんにちは": "hello",
  "りんご": "apple",
  "ねこ": "cat",
  "いぬ": "dog",
  "辞書": "dictionary",
 }

# 単語のキーを問題として順に表示させるために、キーだけリストにして、現在の単語のインデックスとスコアを初期化
word_keys = list(word.keys())
current_word = 0
score = 0

# ユーザーの解答をチェックする関数
def check_answer():
    # 変数を関数内で使用するために、ここでグローバル宣言
    global current_word,score

    # 入力欄にユーザーが入力した解答を取得し、前後の空白を削除して小文字に変換
    answer = entry.get().lower().strip()

    # ユーザーの解答と正解を比較し、正解ならスコアを1点加算し、正解・不正解のメッセージを表示
    if answer == word[word_keys[current_word]]: # 問題をキーにして、辞書から正解の英単語を取得して比較
        messagebox.showinfo("正解", "正解です！")
        score += 1
    else:
        messagebox.showerror("不正解", f"不正解,正解は {word[word_keys[current_word]]} です。")

    current_word +=1

    # 次の問題を表示するか、ゲーム終了のメッセージを表示するかを判断
    if current_word < len(word):
        label.config(text=word_keys[current_word])
        entry.delete(0, tk.END)
    else:
        messagebox.showinfo("終了", f"ゲーム終了！あなたのスコアは {score} / {len(word)} です。")
        root.destroy()  

# --- GUIのセットアップ ---
root = tk.Tk()
root.title("翻訳アプリ")
root.geometry("300x200")

# 最初の問題を表示するラベル
label=tk.Label(root, text=word_keys[current_word], font=("Arial", 24))
label.pack(pady=20)

# ユーザーが解答を入力するエントリーウィジェットを配置し、Enterキーで解答をチェックできるようにバインド
entry=tk.Entry(root, font=("Arial", 14))
entry.pack(pady=10)
entry.bind("<Return>", lambda event: check_answer()) 

# 解答をチェックするボタンも配置 
button=tk.Button(root, text="解答", command=check_answer)
button.pack()

# GUIのメインループを開始
root.mainloop()
