import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import simpledialog

# 日本語表示の設定（Windows環境を想定）
plt.rcParams['font.family'] = 'MS Gothic'

# 設定
years = [2021, 2022, 2023, 2024, 2025]

# 画面には出さないメインウィンドウを隠して作成
root = tk.Tk()
root.withdraw()

# 入力ダイアログを表示
target_city = simpledialog.askstring("市町村入力", "検索したい市区町村名を入力してください（例：渋谷区）")

# キャンセルされた場合の処理
if not target_city:
    print("入力がキャンセルされました。")
    exit()

population_trend = []
male_pop_trend = []
female_pop_trend = []

# 今動かしているファイルのパスを基準にデータパスを取得
# 親フォルダ(src)のさらに親(Project)へ移動し、dataフォルダ内のファイルパスを作成
# .parent をつなげることで上の階層へ移動できます
base_path = Path(__file__).parent.parent /  "juki_population_raw"

for year in years:

    file_name = base_path / f"juki_{year}_estat.xlsx"
    file_path = base_path / file_name

# ファイルを読み込む 全部読み込む場合
#    df = pd.read_excel(file_path,header=None)

# 読み込み（A〜G列のみ）
    df = pd.read_excel(file_path, header=None, usecols="A:G")

# 「市区町村名」が「熊谷」に一致する行の「男人口」と「女人口」を取得
# 必要なデータ（7行目以降、7列目まで）を抽出（copy()メソッドを使って、別オブジェクトとしてあつかう）
# データ整形（7行目以降を抽出し、最初の7列を確定させて名前付け）
    data_df = df.iloc[6:, :7].copy()
# 列に分かりやすい名前をつける
    data_df.columns = ['団体コード', '都道府県名', '市区町村名', '人口_男', '人口_女', '人口_計', '世帯数']

#特定の市区町村名で検索して、人口（計）を取り出す
    #人口だけを取り出す場合はこの段階で1次元配列(Series)として取り出す（
    #match_row= data_df.loc[data_df['市区町村名'] == target_city, '人口_計']
    # print(type(match_row)) の結果は<class 'pandas.Series'>

    #男女別人口等、複数のデータを取り出す場合は行ごと（DataFrame）取り出す（
    match_row= data_df.loc[data_df['市区町村名'] == target_city]
    # print(type(match_row)) の結果は<class 'pandas.DataFrame'>

    if not match_row.empty:
    #    print(f"{target_city} の合計人口は {match_row.values[0]} 人です。")
    #    pop_value = pd.to_numeric(match_row.values[0], errors='coerce')
    #    population_trend.append(pop_value)
        population_trend.append(pd.to_numeric(match_row['人口_計'].values[0], errors='coerce'))
        male_pop_trend.append(pd.to_numeric(match_row['人口_男'].values[0], errors='coerce'))
        female_pop_trend.append(pd.to_numeric(match_row['人口_女'].values[0], errors='coerce'))
    else:
    #    population_trend.append(None)
    #    print(f"{year}年のデータに {target_city} は見つかりませんでした。")
        for lst in [population_trend, male_pop_trend, female_pop_trend]:
            lst.append(None)

# --- グラフの描画 ---
""" 縦軸が一つしかない前提のお手軽版
plt.figure(figsize=(10, 6)) 


# 合計人口のみををプロット
#plt.plot(years, population_trend, marker='o', linestyle='-', color='b')
# 3本の線をプロット（labelを指定するのがポイント）
plt.plot(years, population_trend, marker='o', label='合計', linewidth=2, color='black')
plt.plot(years, male_pop_trend, marker='s', label='男性', linestyle='--', color='blue')
plt.plot(years, female_pop_trend, marker='^', label='女性', linestyle='--', color='red')

plt.title(f"{target_city} の人口推移 (2021-2025)")
plt.xlabel("年")
plt.ylabel("合計人口")
plt.grid(True)
plt.xticks(years)  # X軸を整数（年）に固定

# 凡例（labelを表示する箱）を表示
plt.legend()
"""
# 右側に軸を追加
fig, ax1 = plt.subplots(figsize=(10, 6)) # ax1 が左軸（合計用）

# 1. 左軸（合計）をプロット
ax1.plot(years, population_trend, marker='o', label='合計', linewidth=2, color='black')
ax1.set_ylabel("合計人口", fontsize=12)
ax1.set_xlabel("年")

# 2. 右軸（男女用）を作成
ax2 = ax1.twinx() 
ax2.plot(years, male_pop_trend, marker='s', label='男性', linestyle='--', color='blue')
ax2.plot(years, female_pop_trend, marker='^', label='女性', linestyle='--', color='red')
ax2.set_ylabel("男女別人口", fontsize=12)

# 3. グラフの装飾
plt.title(f"{target_city} の人口推移 (2-axis)", fontsize=14)
ax1.set_xticks(years)
ax1.grid(True, alpha=0.3)

# 4. 凡例をまとめる（軸が分かれるので少し工夫が必要）
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc='center right') # まとめて表示
plt.show()    