import requests
from pathlib import Path

BASE_URL = "http://mon-serveur:8080"

DOWNLOAD_DIR = Path("images")
DOWNLOAD_DIR.mkdir(exist_ok=True)

response = requests.get(f"{BASE_URL}/count")
count = response.json()["count"]
print("Nombre d'images à télécharger : ", count)

for i in range(count):
    image_name = "jpeg" + str(i)
    url = f"{BASE_URL}/image/{image_name}"

    print("Téléchargement :", image_name)

    r = requests.get(url)

    if r.status_code == 200:

        filepath = DOWNLOAD_DIR / image_name

        with open(filepath, "wb") as f:
            f.write(r.content)

    else:
        print("Erreur téléchargement :", image_name)