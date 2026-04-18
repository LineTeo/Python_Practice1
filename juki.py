"""
fetch_juki_population.py
------------------------
住民基本台帳に基づく人口（市区町村別・総計）を過去5年分まとめて取得し
CSV に保存するスクリプト。

【戦略】
  - APIで市区町村ごとにリクエストするのではなく、
    総務省／e-Stat が公開している「全国一括Excelファイル」を年ごとに
    ダウンロードして pandas で読み込む方式。
  - 令和7年（2025年）: 総務省サイトから直接取得
  - 令和3〜6年（2021〜2024年）: e-Stat API でファイル一覧を取得→ダウンロード

【出力】
  juki_population_raw/   … 年ごとのダウンロードExcelを保存（キャッシュ）
  juki_population.csv    … 縦長（tidy）形式: 団体コード, 都道府県名, 市区町村名,
                            年, 総人口（男）, 総人口（女）, 総人口（計）

【実行方法】
  pip install requests pandas openpyxl tqdm
  python fetch_juki_population.py
  python fetch_juki_population.py --years 2023 2024 2025   # 年を絞る
  python fetch_juki_population.py --out mydata.csv          # 出力ファイル名変更

【注意】
  各Excelのシート構成・ヘッダー行は年によって異なる場合があります。
  読み込み失敗時はエラーメッセージを表示しますが処理は続行します。
  正常に取得できた年のデータのみ出力されます。
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional
import requests
import pandas as pd

# ─── 設定 ──────────────────────────────────────────────────────────────

# 令和7年（2025年）は総務省サイトから直接ダウンロード
# 【総計】令和7年住民基本台帳人口・世帯数（市区町村別）
SOUMU_2025_URL = "https://www.soumu.go.jp/main_content/001023714.xlsx"

# 令和3〜6年は e-Stat API でファイルを検索してダウンロード
# 統計コード: 00200241（住民基本台帳人口・世帯数調査）
ESTAT_APP_ID  = "11bdee7caad9dda40c4a69e112e5bbb14386d380"
ESTAT_LIST_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getDataCatalog"
ESTAT_FILE_URL = "https://api.e-stat.go.jp/rest/3.0/app/getSimpleStatsData"

# e-Stat での年ごとのファイルIDを直接指定（変更になった場合は更新してください）
# 「【総計】市区町村別 人口・世帯数」に相当するファイル
# ※ e-Stat のファイルIDは URL 末尾 /files/... から確認できます
ESTAT_FILE_IDS: dict[int, str] = {
    # 年: e-Stat statsDataId または直接ダウンロードURL
    # 以下は総務省報道ページから確認したExcel直接URL（e-Statに移管済み分）
    2025: "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040306653&fileKind=0",
    2024: "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040306672&fileKind=0",
    2023: "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040306647&fileKind=0",
    2022: "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032224636&fileKind=0",
    2021: "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040306659&fileKind=0"
}

# ダウンロードしたExcelを保存するフォルダ
RAW_DIR = Path("juki_population_raw")

# 読み込み設定（年によってヘッダー行が異なる場合がある）
# header=None で全部読んでから列名を手動特定する方式を採用
SKIP_ROWS_DEFAULT = 2   # 最初の数行はタイトル等

# ─────────────────────────────────────────────────────────────────────


def download_excel(url: str, dest: Path, session: requests.Session) -> bool:
    """Excelファイルをダウンロードして dest に保存する。成功したら True。"""
    if dest.exists():
        print(f"  [skip] キャッシュあり: {dest.name}")
        return True
    try:
        resp = session.get(url, timeout=(10, 60))
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type.lower() and len(resp.content) < 50_000:
            print(f"  [error] HTMLが返ってきました（URLを確認してください）: {url}")
            return False
        dest.write_bytes(resp.content)
        print(f"  [ok] ダウンロード完了: {dest.name} ({len(resp.content):,} bytes)")
        return True
    except requests.RequestException as e:
        print(f"  [error] ダウンロード失敗: {e}")
        return False


def find_header_row(df_raw: pd.DataFrame) -> int:
    """
    'コード' や '市区町村' などのキーワードを含む行をヘッダー行として検出する。
    見つからなければ 0 を返す。
    """
    keywords = ["コード", "都道府県", "市区町村", "団体"]
    for i, row in df_raw.iterrows():
        row_str = " ".join(str(v) for v in row.values if pd.notna(v))
        if any(kw in row_str for kw in keywords):
            return int(i)
    return 0


def find_population_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    """
    列名から「総人口（計・男・女）」に相当する列を特定する。
    返り値: {"total": col, "male": col, "female": col}
    """
    cols = df.columns.tolist()
    result: dict[str, Optional[str]] = {"total": None, "male": None, "female": None}

    for col in cols:
        s = str(col)
        # 男女計の総人口
        if result["total"] is None and ("計" in s or "合計" in s) and "人口" in s:
            result["total"] = col
        # 男
        if result["male"] is None and "男" in s and "人口" in s and "女" not in s:
            result["male"] = col
        # 女
        if result["female"] is None and "女" in s and "人口" in s and "男" not in s:
            result["female"] = col

    # フォールバック: 列名に人口が入っていない場合、数値列の先頭3つを使う
    if result["total"] is None:
        num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) >= 3:
            result["total"], result["male"], result["female"] = num_cols[0], num_cols[1], num_cols[2]

    return result


def find_code_and_name_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    """市区町村コード列・都道府県名列・市区町村名列を特定する。"""
    cols = df.columns.tolist()
    result: dict[str, Optional[str]] = {"code": None, "pref": None, "city": None}

    for col in cols:
        s = str(col)
        if result["code"] is None and ("コード" in s or "団体" in s or "code" in s.lower()):
            result["code"] = col
        if result["pref"] is None and "都道府県" in s:
            result["pref"] = col
        if result["city"] is None and "市区町村" in s and "都道府県" not in s:
            result["city"] = col

    return result


def read_excel_population(path: Path, year: int) -> Optional[pd.DataFrame]:
    """
    ダウンロードしたExcelを読み込み、以下の列を持つDataFrameを返す:
      団体コード, 都道府県名, 市区町村名, 年, 総人口_計, 総人口_男, 総人口_女
    """
    print(f"  Excelを読み込み中: {path.name}")

    # まず全部読んでヘッダー行を探す
    try:
        df_raw = pd.read_excel(path, header=None, sheet_name=0, engine="openpyxl")
    except Exception as e:
        print(f"  [error] Excel読み込みエラー: {e}")
        return None

    header_row = find_header_row(df_raw)
    print(f"  ヘッダー行推定: {header_row}行目")

    try:
        df = pd.read_excel(
            path,
            header=header_row,
            sheet_name=0,
            engine="openpyxl",
            dtype=str,  # まず全部文字列で読む
        )
    except Exception as e:
        print(f"  [error] Excel再読み込みエラー: {e}")
        return None

    # 空行・空列を除去
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # 列特定
    id_cols  = find_code_and_name_columns(df)
    pop_cols = find_population_columns(df)

    print(f"  列マッピング: コード={id_cols['code']}, 都道府県={id_cols['pref']}, "
          f"市区町村={id_cols['city']}, 計={pop_cols['total']}, "
          f"男={pop_cols['male']}, 女={pop_cols['female']}")

    if pop_cols["total"] is None:
        print(f"  [warn] 総人口列が見つかりませんでした。列一覧: {df.columns.tolist()[:20]}")
        return None

    # 必要な列だけ抽出
    keep: dict[str, str] = {}
    if id_cols["code"]:
        keep["団体コード"] = id_cols["code"]
    if id_cols["pref"]:
        keep["都道府県名"] = id_cols["pref"]
    if id_cols["city"]:
        keep["市区町村名"] = id_cols["city"]
    if pop_cols["total"]:
        keep["総人口_計"] = pop_cols["total"]
    if pop_cols["male"]:
        keep["総人口_男"] = pop_cols["male"]
    if pop_cols["female"]:
        keep["総人口_女"] = pop_cols["female"]

    df_out = df[[v for v in keep.values() if v in df.columns]].copy()
    df_out.columns = [k for k, v in keep.items() if v in df.columns]

    # 数値変換（カンマ・スペース除去）
    for col in ["総人口_計", "総人口_男", "総人口_女"]:
        if col in df_out.columns:
            df_out[col] = (
                df_out[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace(" ", "", regex=False)
                .str.strip()
            )
            df_out[col] = pd.to_numeric(df_out[col], errors="coerce")

    # コード列を文字列で正規化（5桁ゼロ埋め）
    if "団体コード" in df_out.columns:
        df_out["団体コード"] = (
            df_out["団体コード"]
            .astype(str)
            .str.strip()
            .str.replace(".0", "", regex=False)
            .str.zfill(5)
        )

    # 総人口が NaN の行（ヘッダー残骸・合計行など）を除去
    df_out = df_out.dropna(subset=["総人口_計"])
    df_out = df_out[df_out["総人口_計"] > 0]

    df_out["年"] = year
    df_out = df_out.reset_index(drop=True)
    print(f"  → {len(df_out):,} 行取得")
    return df_out


def main():
    parser = argparse.ArgumentParser(description="住民基本台帳人口 一括ダウンロード＆整形")
    parser.add_argument(
        "--years", nargs="+", type=int,
        default=[2021, 2022, 2023, 2024, 2025],
        help="取得する年（デフォルト: 2021〜2025）"
    )
    parser.add_argument(
        "--out", default="juki_population.csv",
        help="出力CSVファイル名"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="キャッシュを無視して再ダウンロード"
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; juki-fetcher/1.0)"
    })

    all_dfs = []

    for year in sorted(args.years):
        print(f"\n=== {year}年 ===")

        # ダウンロードURLを決定
 #       if year == 2025:
 #           url  = SOUMU_2025_URL
 #           dest = RAW_DIR / f"juki_{year}_soumu.xlsx"
 #       el
        if year in ESTAT_FILE_IDS:
            url  = ESTAT_FILE_IDS[year]
            dest = RAW_DIR / f"juki_{year}_estat.xlsx"
        else:
            print(f"  [skip] {year}年のURLが未設定です")
            continue

        # キャッシュ削除オプション
        if args.no_cache and dest.exists():
            dest.unlink()

        # ダウンロード
        ok = download_excel(url, dest, session)
        if not ok:
            print(f"  [skip] {year}年はスキップします")
            continue

        time.sleep(0.5)  # サーバー負荷軽減

        # 読み込み＆整形
        df = read_excel_population(dest, year)
        if df is not None and len(df) > 0:
            all_dfs.append(df)
        else:
            print(f"  [warn] {year}年: データ取得に失敗しました")

    if not all_dfs:
        print("\nデータが1件も取得できませんでした。URLやファイルIDを確認してください。")
        sys.exit(1)

    # 縦結合
    df_all = pd.concat(all_dfs, ignore_index=True)

    # 列順を整理
    col_order = ["年", "団体コード", "都道府県名", "市区町村名",
                 "総人口_計", "総人口_男", "総人口_女"]
    df_all = df_all[[c for c in col_order if c in df_all.columns]]
    df_all = df_all.sort_values(["年", "団体コード"], ignore_index=True)

    # 保存
    out_path = Path(args.out)
    df_all.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 保存完了: {out_path}  ({len(df_all):,} 行)")

    # サマリー
    print("\n── サマリー ──")
    summary = df_all.groupby("年").agg(
        市区町村数=("団体コード", "count"),
        総人口合計=("総人口_計", "sum"),
    )
    print(summary.to_string())
    print()
    print("注: e-StatのファイルIDは更新される場合があります。")
    print("    取得失敗した年は ESTAT_FILE_IDS の URL を最新のものに書き換えてください。")
    print(f"    ダウンロード済みExcelは {RAW_DIR}/ に保存されています（再実行時は再利用されます）。")


if __name__ == "__main__":
    main()