import time
import random
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
STORIA_DIR.mkdir(parents=True, exist_ok=True)

MARKER = "__NEXT_DATA__"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Faculty Project)"
}

def get_next_data(url):
    response = requests.get(url, headers=HEADERS, timeout=30)

    response.raise_for_status()

    start = response.text.find(MARKER)
    json_start = response.text.find(">", start)
    json_end = response.text.find("</script>", json_start)
    json_text = response.text[json_start + 1:json_end]
    data = json.loads(json_text)
    return data

def download_data(item_id, item_slug):
    path_id = STORIA_DIR / f"{item_id}.json"
    if path_id.exists():
        print(f"Data for item {item_id} already exists. Skipping download.")
        return
    data = get_next_data(BASE_URL + item_slug)
    ad = data["props"]["pageProps"].get("ad")
    if ad is None:
        print(f"No ad data found for item {item_id}. Skipping download.")
        return
    for key in ("images", "listingImages", "owner", "contactDetails", "agency",
            "userAdverts", "seo", "floorPlans", "videos"):
        ad.pop(key, None)
    with open(path_id, "w", encoding="utf-8") as f:
        json.dump(ad, f, ensure_ascii=False)
    print(item_id, "saved")
    time.sleep(random.uniform(1.5, 3.0)) 

def main():
    data = get_next_data(URL)
    # items = data["props"]["pageProps"]["data"]["searchAds"]["items"]

    pagination = data["props"]["pageProps"]["data"]["searchAds"]["pagination"]
    number_of_pages = pagination["totalPages"]

    number_of_pages = number_of_pages

    for page in range(number_of_pages):
        str_for_page = URL + PAGE_PAD + str(page + 1)

        try:
            data = get_next_data(str_for_page)
        except (requests.RequestException, ValueError) as e:
            print("error at page", page + 1, e)
            continue

        items = data["props"]["pageProps"]["data"]["searchAds"]["items"]
        for item in items:
            try:
                download_data(item["id"], item["slug"])
            except (requests.RequestException, ValueError) as e:
                print("errors at", item["id"], e)
        time.sleep(random.uniform(1.5, 3.0)) 

if __name__ == "__main__":
    main()
