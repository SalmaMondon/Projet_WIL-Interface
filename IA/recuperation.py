import requests
from pathlib import Path

BASE_URL = "http://10.179.218.179:80"

DOWNLOAD_DIR = Path("IA/images")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# response = requests.get(f"{BASE_URL}/count")
# count = response.json()["count"]
# print("Nombre d'images à télécharger : ", count)
count = 50

for i in range(count):
    image_name = str(i)
    url = f"{BASE_URL}/image/{image_name}"

    print("Téléchargement :", image_name)

    r = requests.get(url)

    if r.status_code == 200:

        filepath = DOWNLOAD_DIR / (image_name + ".jpg")

        with open(filepath, "wb") as f:
            f.write(r.content)

    else:
        print("Erreur téléchargement :", image_name)