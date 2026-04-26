import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# matplotlibのデフォルトフォントは日本語非対応のため、MS Gothicを指定する。
# これを設定しないとグラフの日本語ラベルが□（豆腐）になる。
plt.rcParams['font.family'] = 'MS Gothic'

# ============================================================
# 設定
# ============================================================
LATITUDE_DEG = 36.15  # 熊谷市の緯度。理論的可照時間の計算に使用する。

# ============================================================
# Step 0. データ読み込み
# ============================================================
# skiprows=3 は気象庁CSVのヘッダー行（説明文など）を読み飛ばすための指定。
df = pd.read_csv('Climate_data.csv', encoding='shift-jis', skiprows=3)

# 日付列をpandasのdatetime型に変換する。
# datetime型にすることで、年・月・日の抽出や日付演算が容易になる。
df['date'] = pd.to_datetime(df['date'], format='%Y/%m/%d')

# 日付順に並べ直し、インデックスを0からの連番に振り直す。
# reset_index(drop=True) は元のインデックス列をDataFrameに残さず捨てるオプション。
df = df.sort_values('date').reset_index(drop=True)

# 各列を数値型に変換する。
# 気象庁CSVでは欠測値が「---」や「*」などの文字列で記録されていることがある。
# errors='coerce' を指定することで、数値に変換できない値をエラーにせずNaNに置き換える。
# NaNになった行は後続の計算（回帰など）で自動的に除外される。
for col in ['temperature', 'sunshine', 'rain', 'wind']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# ============================================================
# Step 1. 理論的可照時間（Spencer式）
# ============================================================
# 「理論的可照時間」とは、大気や雲が一切なく完全に快晴だった場合の
# 日の出から日の入りまでの時間のこと。
# これは緯度と日付だけで天文学的に計算できる純粋な季節成分であり、
# 実測の日照時間から季節要因を分離するための基準値として使用する。
#
# Spencer式は太陽赤緯（地球の公転による太陽の傾き）を精度よく近似する
# 実用的な計算式で、気象・農業分野で広く使われている。
def calc_theoretical_sunshine(dates, latitude_deg):
    # 緯度を度からラジアンに変換する。
    # 三角関数（np.sin, np.cos, np.tan）はラジアン単位を要求するため。
    lat = np.radians(latitude_deg)
    results = []
    for date in dates:
        # その年の何日目かを取得する（1月1日=1、12月31日=365または366）。
        doy = date.timetuple().tm_yday

        # Spencer式の角度パラメータB（年間を2πラジアンに対応させた値）。
        B = 2 * np.pi * (doy - 1) / 365

        # 太陽赤緯δ（ラジアン）をSpencer式で計算する。
        # 太陽赤緯とは、地球の公転軌道の傾きにより生じる「太陽が真南から
        # どれだけ南北にずれているか」を表す角度。
        # 夏至に最大（+23.4°）、冬至に最小（-23.4°）となり、
        # これが季節による日照時間の変化をもたらす主要因。
        decl = (0.006918
                - 0.399912 * np.cos(B)    + 0.070257 * np.sin(B)
                - 0.006758 * np.cos(2*B)  + 0.000907 * np.sin(2*B)
                - 0.002697 * np.cos(3*B)  + 0.001480 * np.sin(3*B))

        # 日没時角H0のコサイン値を計算する。
        # 時角とは、太陽が南中（真南の最高点）を基準としてどの位置にあるかを
        # 角度で表したもの。日没時角は太陽が地平線に沈む瞬間の時角に対応する。
        # この式は「太陽が地平線ちょうどにある」条件から導出される。
        cos_H0 = -np.tan(lat) * np.tan(decl)

        # 白夜・極夜の処理。
        # cos_H0 < -1 は「太陽が一日中沈まない（白夜）」を意味する。
        # cos_H0 >  1 は「太陽が一日中昇らない（極夜）」を意味する。
        # 熊谷市（緯度36°）ではこの条件は発生しないが、汎用性のため記述している。
        if cos_H0 < -1:
            T = 24.0
        elif cos_H0 > 1:
            T = 0.0
        else:
            # arccos(cos_H0) でH0（ラジアン）を求め、度に変換後、時間に換算する。
            # 地球は24時間で360°自転するため、1時間あたり15°に相当する。
            # 「2 * H0」は日出から日没までの全時角（日没時角の左右対称分）。
            T = 2 * np.degrees(np.arccos(cos_H0)) / 15
        results.append(T)

    # リストをNumPy配列に変換して返す。
    # NumPy配列はpandasのDataFrame列に直接代入できる。
    return np.array(results)

df['theoretical_sunshine'] = calc_theoretical_sunshine(df['date'], LATITUDE_DEG)

# ============================================================
# Step 2. 日照比率と偏差（季節成分除去）
# ============================================================
# 【設計の考え方】
# 実測日照時間には「季節要因（夏は長く冬は短い）」と「気象要因（晴れ・曇り・雨）」
# の両方が混在している。このまま気温の回帰に使うと、日照の季節変動が
# 気温の季節変動とクロストークしてしまう。
#
# そこで、天文学的に求まる理論値（純粋な季節成分）で実測値を割ることで、
# 「その日が季節的に見てどれだけ晴れていたか」という比率（0〜1）を求める。
# この比率には季節成分がほぼ含まれないため、気象要因の指標として使える。
#
# さらに、比率の月日平均（梅雨時期は曇りやすい、など気候的傾向）も
# 気温の月日平均に既に反映されているとみなし、温度の季節要因として吸収する。
# 月日平均からの偏差だけを気象要因（年ごとの晴れ・曇りのばらつき）として使用する。

# 理論的可照時間がほぼ0の日（日の出がほとんどない日）は
# 分母が極端に小さくなり比率が不安定になるため、NaNとして除外する。
df['sunshine_ratio'] = np.where(
    df['theoretical_sunshine'] > 0.5,
    df['sunshine'] / df['theoretical_sunshine'],
    np.nan
)

# 月日ごとの日照比率の20年平均を計算する。
# これは「その月日は統計的に晴れやすい/曇りやすい」という気候的傾向を表す。
# この傾向は気温の月日平均にも反映されているため、季節要因として吸収する。
# strftime('%m-%d') で月日を「01-01」のような文字列に変換してグループ化する。
df['month_day'] = df['date'].dt.strftime('%m-%d')
# groupby で同じ月日のデータをグループ化し、transform('mean') で
# 各行にそのグループの平均値を対応させる（行数はそのまま保持される）。
df['sunshine_ratio_avg'] = df.groupby('month_day')['sunshine_ratio'].transform('mean')

# 日照比率から月日平均を引いた偏差が、純粋な気象変動（年ごとの晴れ・曇りのばらつき）。
# この値が正なら「その日は気候的傾向より晴れていた」、負なら「曇りがちだった」を意味する。
df['sunshine_anomaly'] = df['sunshine_ratio'] - df['sunshine_ratio_avg']

# ============================================================
# Step 3. 気温の季節要因除去
# ============================================================
# 月日ごとの気温平均を季節要因として定義する。
# この平均値には「日照の季節パターンに乗った温度上昇」も含まれているが、
# それは「その地点の気候」として季節要因に吸収する（Step 2の設計と整合）。
# つまり、Step 2で日照の季節成分を除去した後の偏差のみを気象要因として扱うことで、
# 気温とのクロストークを防ぐ設計になっている。
df['temp_avg'] = df.groupby('month_day')['temperature'].transform('mean')

# 気温偏差 = 実測気温 − 月日平均気温。
# この偏差には「長期トレンド」と「気象要因（日照・降水・風速）」が混在している。
# Step 4でさらに気象要因を除去することで、長期トレンドだけを取り出す。
df['temp_anomaly'] = df['temperature'] - df['temp_avg']

# ============================================================
# Step 4. 月ごとに重回帰（気象要因→気温偏差）
# ============================================================
# 【設計の考え方】
# 日照が気温に与える影響は季節によって異なる（夏の日差しは強く、冬は弱い）。
# 降水・風速も同様に季節によって気温への感度が変わりうる。
# そのため、1〜12月それぞれで別々に回帰係数を推定する。
#
# 各月のデータ数は「約20年 × 約30日 = 約600件」となり、
# 3変数の重回帰には十分なサンプル数が確保できる。
#
# 重回帰式：temp_anomaly = β0 + β1×sunshine_anomaly + β2×rain + β3×wind
# β1〜β3 が気象要因の影響を表す係数。
# この式で推定した値（気象要因による気温変動）を temp_anomaly から引くことで、
# 気象補正済みの気温偏差を得る。

df['month'] = df['date'].dt.month
# 後で各行に補正値を格納するため、NaNで初期化した列を用意する。
df['temp_corrected'] = np.nan
df['temp_weather_effect'] = np.nan  # 気象要因による気温への寄与（確認用）

feature_cols = ['sunshine_anomaly', 'rain', 'wind']
coef_records = []  # 月別の回帰係数を記録するリスト

for month in range(1, 13):
    # 対象月のデータを抽出する。
    mask = df['month'] == month
    # 説明変数・目的変数のいずれかにNaNがある行を除いて回帰用データを作成する。
    # dropna は指定列にNaNがある行を削除したコピーを返す（元のdfは変更されない）。
    subset = df[mask].dropna(subset=feature_cols + ['temp_anomaly'])

    if len(subset) < 30:
        print(f"{month}月: データ不足のためスキップ")
        continue

    # 説明変数行列Xと目的変数ベクトルyを作成する。
    # .values でpandasのSeries/DataFrameをNumPy配列に変換する。
    # LinearRegressionはNumPy配列を要求するため。
    X = subset[feature_cols].values
    y = subset['temp_anomaly'].values

    # scikit-learnの線形回帰モデルを学習する。
    # fit() が最小二乗法で回帰係数を推定する。
    model = LinearRegression()
    model.fit(X, y)

    # 月別の回帰係数・切片・決定係数R²を記録する。
    # R²（決定係数）は0〜1の値をとり、1に近いほど回帰モデルの当てはまりが良い。
    # R²が低い月は気象3要因では説明しきれない変動が多いことを示す。
    coef_records.append({
        'month': month,
        'coef_sunshine_anomaly': model.coef_[0],
        'coef_rain':             model.coef_[1],
        'coef_wind':             model.coef_[2],
        'intercept':             model.intercept_,
        'r2':                    model.score(X, y),
        'n':                     len(subset)
    })

    # 回帰係数はNaN除外データで学習したが、補正値は全月データに対して計算する。
    # NaNのある行は計算対象から外すため、全説明変数がnotnaの行だけを対象にする。
    all_mask = mask & df[feature_cols].notna().all(axis=1)
    X_all = df.loc[all_mask, feature_cols].values

    # 気象効果 = X @ coef + intercept（行列積による予測値の一括計算）。
    # @ 演算子はNumPyの行列積（matmul）を表す。
    # これは「sunshine_anomaly×β1 + rain×β2 + wind×β3 + β0」を全行に対して計算する。
    weather_effect = X_all @ model.coef_ + model.intercept_

    df.loc[all_mask, 'temp_weather_effect'] = weather_effect
    # 気象補正済み気温偏差 = 気温偏差 − 気象要因による寄与。
    # これが「長期トレンド」成分に相当する。
    df.loc[all_mask, 'temp_corrected'] = (
        df.loc[all_mask, 'temp_anomaly'] - weather_effect
    )

coef_df = pd.DataFrame(coef_records).set_index('month')
print("\n=== 月別回帰係数 ===")
print(coef_df.round(4).to_string())

# ============================================================
# Step 5. 年平均トレンド
# ============================================================
df['year'] = df['date'].dt.year

# 年ごとに気温偏差（補正前後）の平均を集計する。
# agg() に辞書形式で「新列名=(元列名, 集計関数)」を指定するpandasの記法。
annual = df.groupby('year').agg(
    temp_anomaly_mean    = ('temp_anomaly',    'mean'),
    temp_corrected_mean  = ('temp_corrected',  'mean'),
).reset_index()

# 線形トレンドを計算する関数。
# np.polyfit で最小二乗法による1次多項式（直線）の係数を求める。
# 返り値 p は [傾き, 切片] の配列。
# np.poly1d(p) は多項式オブジェクトを生成し、(x) で各xに対する予測値を返す。
def linear_trend(x, y):
    mask = ~np.isnan(y)  # NaNを除外して計算する
    p = np.polyfit(x[mask], y[mask], 1)
    return p, np.poly1d(p)(x)

years = annual['year'].values
p_raw,  trend_raw  = linear_trend(years, annual['temp_anomaly_mean'].values)
p_corr, trend_corr = linear_trend(years, annual['temp_corrected_mean'].values)

# p[0] が傾き（1年あたりの変化量）。10年あたりに換算して表示する。
print(f"\n=== 長期トレンド ===")
print(f"補正前：{p_raw[0]*10:+.3f} ℃/10年")
print(f"補正後：{p_corr[0]*10:+.3f} ℃/10年")

# ============================================================
# Step 6. グラフ表示
# ============================================================
# 4段構成で各処理ステップの結果を可視化する。
fig, axes = plt.subplots(4, 1, figsize=(16, 18))

# --- 上段：日照比率と偏差（Step 2の確認） ---
ax1 = axes[0]
ax1.plot(df['date'], df['sunshine_ratio'],       color='gold',       linewidth=0.5, alpha=0.5, label='日照比率')
ax1.plot(df['date'], df['sunshine_ratio_avg'],   color='darkorange', linewidth=1.0, label='月日平均比率（季節要因）')
ax1.plot(df['date'], df['sunshine_anomaly'],     color='steelblue',  linewidth=0.5, alpha=0.7, label='日照偏差（気象要因）')
ax1.axhline(0, color='gray', linewidth=0.5, linestyle='--')
ax1.set_ylabel('日照比率')
ax1.set_title('日照比率・偏差')
ax1.legend(fontsize=9)
ax1.grid(True, alpha=0.3)

# --- 2段目：月別回帰係数とR²（Step 4の確認） ---
# 棒グラフで各月の回帰係数を表示し、右軸にR²を重ねる。
# 係数の符号が物理的に妥当か確認する（日照↑→気温↑、降水↑→気温↓ など）。
ax2 = axes[1]
month_labels = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
x = coef_df.index.values
width = 0.25
ax2.bar(x - width, coef_df['coef_sunshine_anomaly'], width, label='日照偏差係数', color='gold')
ax2.bar(x,         coef_df['coef_rain'],             width, label='降水量係数',   color='steelblue')
ax2.bar(x + width, coef_df['coef_wind'],             width, label='風速係数',     color='lightgreen')
ax2.axhline(0, color='gray', linewidth=0.5)
ax2.set_xticks(range(1, 13))
ax2.set_xticklabels(month_labels)
ax2.set_ylabel('回帰係数')
ax2.set_title('月別回帰係数（気象要因 → 気温偏差）')
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3, axis='y')

# twinx() で右側に第2のY軸を追加し、R²を折れ線で重ねる。
ax2r = ax2.twinx()
ax2r.plot(coef_df.index, coef_df['r2'], color='red', marker='o', markersize=4,
          linewidth=1, linestyle='--', label='R²')
ax2r.set_ylabel('R²', color='red')
ax2r.tick_params(axis='y', colors='red')
ax2r.set_ylim(0, 1)
ax2r.legend(loc='upper right', fontsize=9)

# --- 3段目：気温偏差の補正前後（Step 4の確認） ---
ax3 = axes[2]
ax3.plot(df['date'], df['temp_anomaly'],   color='lightcoral', linewidth=0.5, alpha=0.6, label='気温偏差（補正前）')
ax3.plot(df['date'], df['temp_corrected'], color='crimson',    linewidth=0.5, alpha=0.8, label='気温偏差（補正後）')
ax3.axhline(0, color='gray', linewidth=0.5, linestyle='--')
ax3.set_ylabel('気温偏差（℃）')
ax3.set_title('気温偏差（補正前後）')
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3)
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax3.xaxis.set_major_locator(mdates.YearLocator(2))

# --- 下段：年平均トレンド（最終結果） ---
# 補正前後の年平均値と線形トレンド直線を重ねて表示する。
# トレンドの傾きが補正によってどう変化したかを確認する。
ax4 = axes[3]
ax4.plot(annual['year'], annual['temp_anomaly_mean'],   'o--', color='lightcoral', markersize=4, label='年平均気温偏差（補正前）')
ax4.plot(annual['year'], annual['temp_corrected_mean'], 'o-',  color='crimson',    markersize=4, label='年平均気温偏差（補正後）')
ax4.plot(years, trend_raw,  '--', color='salmon',  linewidth=1.5,
         label=f'トレンド補正前：{p_raw[0]*10:+.3f}℃/10年')
ax4.plot(years, trend_corr, '-',  color='darkred', linewidth=1.5,
         label=f'トレンド補正後：{p_corr[0]*10:+.3f}℃/10年')
ax4.axhline(0, color='gray', linewidth=0.5, linestyle='--')
ax4.set_ylabel('気温偏差（℃）')
ax4.set_xlabel('年')
ax4.set_title('年平均気温偏差と長期トレンド')
ax4.legend(fontsize=9)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('climate_trend_analysis.png', dpi=150, bbox_inches='tight')
plt.show()

# ============================================================
# 出力：後続処理用配列
# ============================================================
# df['temp_corrected']          : 気象補正済み気温偏差（日次、NaNあり）
# annual['temp_corrected_mean'] : 年平均補正済み気温偏差
