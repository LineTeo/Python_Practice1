import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# 日本語フォント
plt.rcParams['font.family'] = 'MS Gothic'

years = [2021, 2022, 2023, 2024, 2025]
base_path = Path(__file__).parent.parent / "juki_population_raw"

# --- Tkinter ---
# --- メインウィンドウ ---
root = tk.Tk()
# root.withdraw() # 最初のウインドウの中ですべての処理を行ように変更したので、隠す必要がなくなった。最初から表示しておいて、後で内容を入れ替える方式に変更。
root.title("人口推移ツール")
root.geometry("900x600")

# --- 市町村入力エリア ---
""" 旧コードは完全一致しか受け付けない
target_city = simpledialog.askstring("市町村入力", "検索したい市区町村名を入力してください")
if not target_city:
    print("キャンセルされました")
    exit()
"""
# 新コードは不完全一致でも検索し、候補を選択できるようにする

frame_top = tk.Frame(root)
frame_top.pack(pady=10)

tk.Label(frame_top, text="市区町村名:").pack(side=tk.LEFT)

entry = tk.Entry(frame_top, width=20)
entry.pack(side=tk.LEFT, padx=5)

search_btn = tk.Button(frame_top, text="検索")
search_btn.pack(side=tk.LEFT, padx=5)

# --- 候補プルダウン ---
selected_city = tk.StringVar()
combo = ttk.Combobox(root, textvariable=selected_city, state="readonly", width=40)
combo.pack(pady=5)

# --- グラフエリア ---
frame_graph = tk.Frame(root)
frame_graph.pack(fill=tk.BOTH, expand=True)

canvas = None  # 後で使う

# --- 検索処理 ---
def search_city():
    global canvas

    keyword = entry.get()
    if not keyword:
        return

    # 初年度だけで候補取得
    file_path = base_path / f"juki_{years[0]}_estat.xlsx"
    df = pd.read_excel(file_path, header=None, usecols="A:G")
    data_df = df.iloc[6:, :7].copy()
    data_df.columns = ['団体コード', '都道府県名', '市区町村名', '人口_男', '人口_女', '人口_計', '世帯数']

    candidates_df = data_df.loc[data_df['市区町村名'].str.contains(keyword, na=False)]

    if len(candidates_df) == 0:
        combo['values'] = []
        return

    candidates = sorted(set(candidates_df['市区町村名'].tolist()))
    combo['values'] = candidates

    if len(candidates) == 1:
        combo.set(candidates[0])
        draw_graph(candidates[0])

""" 名前の重複があるケースへの対応は、検索機能に統合するので廃止
# --- 候補選択ダイアログ ---
def select_from_candidates(candidates):
    win = tk.Toplevel()
    win.title("候補選択")

    tk.Label(win, text="候補を選択してください").pack(pady=5)

    selected_var = tk.StringVar(win)
    selected_var.set(candidates[0])

    option = tk.OptionMenu(win, selected_var, *candidates)
    option.pack(pady=5)

    result = {"value": None}

    def on_ok():
        result["value"] = selected_var.get()
        win.destroy()

    tk.Button(win, text="OK", command=on_ok).pack(pady=5)

    win.grab_set()
    win.wait_window()

    return result["value"]
"""

# --- グラフ描画 ---
def draw_graph(city_name):
    global canvas

    # --- データ処理 ---
    population_trend = []
    male_pop_trend = []
    female_pop_trend = []


    # selected_name = None

    # for i, year in enumerate(years): # ループの最初で候補選択を行う方式から、検索と候補選択を分ける方式に変更したので、ループの外に出す
    for year in years:
        file_path = base_path / f"juki_{year}_estat.xlsx"
        df = pd.read_excel(file_path, header=None, usecols="A:G")
        data_df = df.iloc[6:, :7].copy()
        data_df.columns = ['団体コード', '都道府県名', '市区町村名', '人口_男', '人口_女', '人口_計', '世帯数']

        """    旧コードはループの最初で候補選択を行う方式だったが、検索と候補選択を分ける方式に変更したので廃止
    if i == 0:
        candidates_df = data_df.loc[data_df['市区町村名'].str.contains(target_city, na=False)]

        if len(candidates_df) == 0:
            print("該当なし")
            exit()

        elif len(candidates_df) > 1:
            candidates = sorted(set(candidates_df['市区町村名'].tolist()))
            selected_name = select_from_candidates(candidates)
        else:
            selected_name = candidates_df['市区町村名'].values[0]
        """
        match_row = data_df.loc[data_df['市区町村名'] == city_name] # 候補選択処理がなくなり、selected_name　→　city_name　に変更

        if not match_row.empty:
            population_trend.append(pd.to_numeric(match_row['人口_計'].values[0], errors='coerce'))
            male_pop_trend.append(pd.to_numeric(match_row['人口_男'].values[0], errors='coerce'))
            female_pop_trend.append(pd.to_numeric(match_row['人口_女'].values[0], errors='coerce'))
        else:
            population_trend.append(None)
            male_pop_trend.append(None)
            female_pop_trend.append(None)
    """ 最初のウインドウで検索からグラフ描画までおこなうのでここは不要
# --- グラフをTkinterに埋め込む ---
# root = tk.Tk() # 新たにつくったら、終わらなくなったので、最初に作ったrootを使いまわす
root.deiconify()   # 表示する
root.title(f"{city_name} の人口推移")
    """

    fig, ax1 = plt.subplots(figsize=(8, 5))

    # 左軸
    ax1.plot(years, population_trend, marker='o', label='合計', linewidth=2)
    ax1.set_ylabel("合計人口")
    ax1.set_xlabel("年")

    # 右軸
    ax2 = ax1.twinx()
    ax2.plot(years, male_pop_trend, marker='s', linestyle='--', label='男性')
    ax2.plot(years, female_pop_trend, marker='^', linestyle='--', label='女性')
    ax2.set_ylabel("男女別人口")

    # 凡例統合
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc='upper left')

    ax1.set_xticks(years)
    ax1.grid(True)

    # --- 既存グラフ削除 ---
    if canvas:
        canvas.get_tk_widget().destroy()


    # Tkinterに描画
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# --- プルダウン選択時 ---
def on_select(event):
    city = selected_city.get()
    if city:
        draw_graph(city)

combo.bind("<<ComboboxSelected>>", on_select)
search_btn.config(command=search_city)

# --- ウィンドウクローズ処理 ---
def on_close():
    root.quit()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()