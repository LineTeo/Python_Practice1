import requests
from typing import Optional
from xml.etree import ElementTree as ET

class EStatApiClient:
    """
    e-Stat API (statsDataId=0003433219) に問い合わせ、
    指定した areaコードの総人口を返すクラス。
    """

    APP_ID        = "11bdee7caad9dda40c4a69e112e5bbb14386d380"
    STATS_DATA_ID = "0003433219"
    BASE_URL      = "https://api.e-stat.go.jp/rest/3.0/app/getStatsData"

    def fetch_population(self, area_code: str) -> Optional[int]:
        """
        areaコードを受け取り、総人口を Optional[int] で返す。
        データなし・通信エラーの場合は None。

        :param area_code: 5桁の地域コード（例: "01100"）
        :return: 総人口（int）または None
        """
        print(f"[EStatApiClient] リクエストするエリアコード : {area_code}")

        params = {
            "appId":       self.APP_ID,
            "statsDataId": self.STATS_DATA_ID,
            "metaGetFlg":  "N",
            "cntGetFlg":   "N",
            "cdArea":      area_code,
        }

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=(5, 10),  # (connect_timeout, read_timeout)
            )

            if response.status_code != 200:
                print(f"[EStatApiClient] HTTPエラー: {response.status_code}")
                return None

            # XMLパース
            root = ET.fromstring(response.content)

            # <VALUE cat01="0" area="xxxxx" ...> の要素を取得
            # cat01="0" が総人口
            for el in root.iter("VALUE"):
                if el.attrib.get("cat01") == "0":
                    text = (el.text or "").strip()
                    return int(text)

        except requests.RequestException as e:
            print(f"[EStatApiClient] 通信エラー: {e}")
        except ET.ParseError as e:
            print(f"[EStatApiClient] XMLパースエラー: {e}")
        except ValueError as e:
            print(f"[EStatApiClient] 数値変換エラー: {e}")

        return None


# --- 動作確認 ---
if __name__ == "__main__":
    client = EStatApiClient()
    area_code = "01100"  # 札幌市
    population = client.fetch_population(area_code)

    if population is not None:
        print(f"総人口: {population:,} 人")
    else:
        print("人口データを取得できませんでした。")