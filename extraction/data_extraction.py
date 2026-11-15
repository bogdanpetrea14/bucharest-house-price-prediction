import requests
import json
from pathlib import Path

BASE_URL = "https://www.storia.ro/ro/oferta/"
PAGE_PAD = "?page="
URL = "https://www.storia.ro/ro/rezultate/vanzare/apartament/bucuresti"
URL2 = "https://www.publi24.ro/anunturi/imobiliare/de-vanzare/apartamente/bucuresti"

ROOT = Path(__file__).resolve().parent.parent  
DATA_DIR = ROOT / "data"
STORIA_DIR = DATA_DIR / "raw" / "storia"

MARKER = "__NEXT_DATA__"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Faculty Project)"
}

def get_next_data(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    start = response.text.find(MARKER)
    json_start = response.text.find(">", start)
    json_end = response.text.find("</script>", json_start)
    json_text = response.text[json_start + 1:json_end]
    data = json.loads(json_text)
    return data

def main():
    data = get_next_data(URL)
    items = data["props"]["pageProps"]["data"]["searchAds"]["items"]

    pagination = data["props"]["pageProps"]["data"]["searchAds"]["pagination"]
    number_of_pages = pagination["totalPages"]

    
    
    # slug = items[0]["slug"]
    # ad_url = BASE_URL + slug
    # print(ad_url)

    # ad_data = get_next_data(ad_url)
    # print(ad_data["props"]["pageProps"]["ad"]["target"])
    # print(ROOT)

if __name__ == "__main__":
    main()