import base64
from pathlib import Path

import requests

url = "http://127.0.0.1:8001/infer/file"
image_path = Path(__file__).resolve().parent / "assets" / "input.jpg"

with image_path.open("rb") as f:
    resp = requests.post(
        url,
        data={"method_name": "retinex"},
        files={"image": (image_path.name, f, "image/jpeg")},
        timeout=60,
    )

print("status_code:", resp.status_code)
resp.raise_for_status()

data = resp.json()
img_bytes = base64.b64decode(data["processed_image_base64"])
with open("processed_from_file.jpg", "wb") as f:
    f.write(img_bytes)

print("saved processed_from_file.jpg")
