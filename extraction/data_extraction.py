import requests
import json

url = "https://www.storia.ro/ro/rezultate/vanzare/apartament/bucuresti"
url2 = "https://www.publi24.ro/anunturi/imobiliare/de-vanzare/apartamente/bucuresti"

marker = "__NEXT_DATA__"

data = {}

headers = {
    "User-Agent": "Mozilla/5.0 (Faculty Project)"
}

response = requests.get(url, headers=headers, timeout=30)

start = response.text.find(marker)

json_start = response.text.find(">", start)
json_end = response.text.find("</script>", json_start)

json_text = response.text[json_start + 1:json_end]

data = json.loads(json_text)

items = data["props"]["pageProps"]["data"]["searchAds"]["items"]
