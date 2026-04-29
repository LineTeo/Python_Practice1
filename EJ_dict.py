import tkinter as tk
from tkinter import messagebox

word = {
  "こんにちは": "hello",
  "りんご": "apple",
  "ねこ": "cat",
  "いぬ": "dog",
  "ありがとう": "thanks",
 }

word_keys = list(word.keys())
current_word = 0
score = 0

def check_answer():
    global current_word,score
    answer = entry.get().lower().strip()

    if answer == word[word_keys[current_word]]:
        messagebox.showinfo("正解", "正解です！")
        score += 1
    else:
        messagebox.showerror("不正解", f"不正解,正解は {word[word_keys[current_word]]} です。")

    current_word +=1
    if current_word < len(word):
        label.config(text=word_keys[current_word])
        entry.delete(0, tk.END)
    else:
        messagebox.showinfo("終了", f"ゲーム終了！あなたのスコアは {score} / {len(word)} です。")
        root.destroy()  

root = tk.Tk()
root.title("翻訳アプリ")
root.geometry("300x200")

label=tk.Label(root, text=word_keys[current_word], font=("Arial", 24))
label.pack(pady=20)
entry=tk.Entry(root, font=("Arial", 14))
entry.pack(pady=10)
button=tk.Button(root, text="解答", command=check_answer)
button.pack()

root.mainloop()
