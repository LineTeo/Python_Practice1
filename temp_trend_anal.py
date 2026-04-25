import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from scipy.optimize import curve_fit

# --- 1. サンプルデータの準備  ---
# pandasを使ってCSVファイルからデータを読み込む
df = pd.read_csv('Climate_data.csv', encoding='shift-jis', skiprows=3)
# dfはpandasのDataFrame型になる

# --- 2. 温度データを抽出  ---
y_temp = df['temp'].values  # 温度データをNumPy配列として取得する。FFTの計算に必要な形式であるため、ここで変数y_tempに格納している。
y_sun = df['sunshine'].values # 日照データも同様にNumPy配列として取得する。
# df['temp']やdf['sunshine']は、pandasのSeries型であるが、.valuesを使うとNumPy配列に変換される。
# 実は、**「PandasはNumPyの上に構築されたライブラリ（ラッパー）」**と言っても過言ではなく、pandasのSeries型は内部的にはNumPy配列を持っている。FFTの計算はNumPyの関数を使うため、データをNumPy配列に変換しておく必要がある。

n = len(df)         # データ点数を取得する。FFTの計算に必要な情報であるため、ここで変数nに格納している。
t = np.arange(n)    # 時間軸を表す配列を生成する。np.arange(n)は、0からn-1までの整数を要素とする1次元配列を生成する関数。FFTの計算で時間軸の情報が必要なため、ここで変数tに格納。

# --- 3. 温度データから季節要因を除去する処理 ---
# 季節要因の除去には、FFTを使ってスペクトル分析を行い、1年周期成分をゼロにする方法を採用する。
# --- 3-1. FFTを実行 ---
y_temp_fft = np.fft.fft(y_temp) #温度データのFFTを計算する。
freq = np.fft.fftfreq(n, d=1) 
# nはデータ点数だが、2のべき数でなくとも適当に補足してくれる 位置引数
# dはサンプリング間隔を指定するキーワード引数。今回は日次データなのでd=1とする。
# np.fft.fftfreqは、FFTの出力に対応する周波数の配列(返り値は多次元配列"ndarray型"だが、実際の返り値は1次元配列)を生成する関数。

# 振幅スペクトル (正の周波数のみ)　複素数として出力されるFFT結果を「振幅（絶対値）」に変換している
amplitude_temp = np.abs(y_temp_fft)
# np.whereは、条件を満たす要素のインデックス(タプル)を返す関数。ここでは、周波数が正の値を持つインデックスを取得している。
pos_indices = np.where(freq > 0)
# ndarray型が持つ「ファンシーインデックス参照」機能により、インデックスを使って正の周波数成分のみを抽出　　
freq_pos = freq[pos_indices]
amplitude_pos_temp = amplitude_temp[pos_indices]
# ここまでで、スペクトルグラフのx軸（周波数）とy軸（振幅）が得られた

# --- 3-2. バンドパス（バンドストップ）フィルタの適用 季節成分の除去 ---
# 1年周期 (1/365) 付近の成分をゼロにする
# 結果からのフィードバックで倍波が出ていることがわかったため、それらも除去することにした。倍波は、基本周波数の整数倍の周波数成分で、非線形な変換や信号の歪みなどによって生成されることがある。

y_temp_fft_filtered = y_temp_fft.copy() #FFTの結果をコピーして、フィルタリング後のスペクトルを格納するための配列を作成する。これにより、元のスペクトルは保持される。
target_freq = 1 / 365.25
margin = 0.001 # フィルタリングする幅

# 1年周期成分を除去（季節要因の排除）
# 1倍波（1年周期）から4倍波（3ヶ月周期）までをループでゼロにする
for i in range(1, 5): 
    harmonic_freq = target_freq * i
    # 正の周波数と負の周波数の両方を対象に、harmonic_freq付近をカット
    mask = np.abs(np.abs(freq) - harmonic_freq) < margin
    y_temp_fft_filtered[mask] = 0
# ndarray型が持つ「ブールインデックス参照」機能により、条件を満たす要素を直接ゼロにしている

# --- 3-3. 逆FFTで時間領域に戻す ---（季節要因を除去したデータを得る）
temp_filtered = np.fft.ifft(y_temp_fft_filtered).real

# --- 4. 日照データから季節要因を除去する処理 ---
# 日照時間の季節要因は温度とは異なり全データから月日ごとの日照時間最大値を求め、それをSINカーブでフィッティングした値を除去する
# 理論日照値は緯度などから論理的に求まるはずだが、算出が複雑なためこの方法を採用。（バンドパスフィルタで除去する方法も試したが、季節成分が完全に除去できなかったため、こちらの方法を採用した。）    
# --- 4-1. 各暦日(1-365)の最大値を取得 ---
# dfに 'day_of_year' カラムを作成（1～365/366の値）
df['day_of_year'] = pd.to_datetime(df['date']).dt.dayofyear
max_sunshine_by_day = df.groupby('day_of_year')['sunshine'].max()

# x（1-365日）, y（その日の最大日照）
x_data = max_sunshine_by_day.index.values
y_data = max_sunshine_by_day.values

# --- 4-2. サインカーブのフィッティング関数定義 ---
def sin_func(x, a, b, c, d):
    # a: 振幅, b: 周期(2π/365), c: 位相ズレ, d: オフセット（平均値）
    return a * np.sin(2 * np.pi / 365 * x + c) + d

# 初期値の推測 [振幅, 周期係数(固定に近い), 位相, 平均]
initial_guess = [5, 1, 0, 7]
params, _ = curve_fit(sin_func, x_data, y_data, p0=initial_guess)

# --- 4-3. 全期間に対する「理想的な日照」の算出 ---
# 全データの日付(day_of_year)に対してサインカーブを適用
df['sun_ideal'] = sin_func(df['day_of_year'], *params)

# --- 4-4. 日照偏差（Residual）の算出 ---
# 実際の日照から、理論上の快晴日照を引く
# これにより「季節性」が完璧に排除された「その日の晴れ具合」が出る
df['sun_deviation'] = df['sunshine'] - df['sun_ideal']
sun_filtered= df['sun_deviation'].values

# --- 5. 重回帰分析による気象要因（日照・雨量・風速）の除去 ---

# 説明変数の準備
# 1. 季節除去済み日照, 2. 雨量(そのもの), 3. 風速(そのもの)
# 雨量や風速はもともと季節周期性が気温ほど支配的ではないため、そのまま使用します。
X_features = np.column_stack([
    sun_filtered, 
    df['rain'].fillna(0).values, 
    df['wind'].fillna(0).values
])
# 説明変数を標準化（平均0、標準偏差1に変換）⇒　重回帰分析の安定性を向上させることができます。
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_features)


# 目的変数は「季節除去済み気温」
y_target = temp_filtered

# モデルの学習
model = LinearRegression()
model.fit(X_scaled, y_target)

# 重回帰モデルによる「予測気温」の算出
# これは「その日の日照・雨量・風速から想定される気温（季節外れな暑さ/寒さ）」を意味する
y_pred = model.predict(X_scaled)

# 「残差（Residual）」の抽出
# 季節成分も、日々の天候の影響も取り除かれた「純粋な変動成分」
residual = y_target - y_pred

# --- 7. 長期トレンド（線形回帰）の算出 ---

# 時間軸を数値(0, 1, 2...)として定義
t_trend = np.arange(len(df)).reshape(-1, 1)

# 残差に対して線形回帰を実行
trend_model = LinearRegression()
trend_model.fit(t_trend, residual)

# トレンド線の算出
trend_line = trend_model.predict(t_trend)

# 傾き（1日あたりの気温上昇率）を取得
slope = trend_model.coef_[0]
# 10年あたりの上昇率に換算 (365.25日 * 10)
slope_10y = slope * 365.25 * 10
# --- 5. 可視化 ---
plt.figure(figsize=(12, 8))

# 温度スペクトル表示
plt.subplot(2, 2, 1) #2行2列のグリッドの1番目の位置にプロットすることを指定
plt.plot(freq_pos, amplitude_pos_temp, label='Temperature')
plt.axvline(target_freq, color='r', linestyle='--', label='1-year cycle')
plt.title("Power Spectrum")
plt.xlabel("Frequency [1/day]")
plt.ylabel("Amplitude")
plt.xlim(0, 0.02) # 周期が長い方（低周波）に注目
plt.legend()

# 日照データとフィッティング結果の表示
plt.subplot(2, 2, 2)
plt.scatter(x_data, y_data, label='Max Sunshine by Day', color='blue', s=10)
x_fit = np.linspace(1, 365, 1000)
y_fit = sin_func(x_fit, *params)
plt.plot(x_fit, y_fit, label='Fitted Sin Curve', color='red')
plt.title("Daily Maximum Sunshine and Fitted Curve")
plt.xlabel("Day of Year")
plt.ylabel("Sunshine")
plt.legend()

# 季節要因除去後のグラフ
plt.subplot(2, 2, 3)
plt.plot(df['date'], y_temp, label='Original', alpha=0.5)
plt.plot(df['date'], temp_filtered, label='Filtered (Seasonal removed)', color='red')
plt.title("Original vs Seasonal Removed")
plt.xlabel("Date")
plt.ylabel("Temperature")
plt.legend()

plt.subplot(2, 2, 4)
plt.plot(df['date'], y_sun, label='Original', alpha=0.5)
plt.plot(df['date'], sun_filtered, label='Filtered (Seasonal removed)', color='red')
plt.title("Original vs Seasonal Removed")
plt.xlabel("Date")
plt.ylabel("Sunshine")
plt.legend()

plt.tight_layout()
plt.show()

# --- 8. 結果の可視化と出力 ---
plt.figure(figsize=(12, 8))

plt.figure(figsize=(12, 6))
plt.plot(df.index, residual, label='Residual (De-seasoned & De-weathered)', color='gray', alpha=0.5)
plt.plot(df.index, trend_line, label=f'Long-term Trend: {slope_10y:.3f} °C/10y', color='red', linewidth=2)

plt.title("Pure Temperature Trend (Linear Regression on Residuals)")
plt.xlabel("Days")
plt.ylabel("Temperature Deviation [°C]")
plt.legend()
plt.grid(True, linestyle='--')
plt.show()

print(f"分析結果:")
print(f"10年あたりの純粋な気温上昇率: {slope_10y:.4f} °C")
print(f"回帰係数 (日照偏差): {model.coef_[0]:.4f}")
print(f"回帰係数 (雨量): {model.coef_[1]:.4f}")
print(f"回帰係数 (風速): {model.coef_[2]:.4f}")