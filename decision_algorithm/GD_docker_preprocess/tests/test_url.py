import base64

import requests

url = "http://127.0.0.1:8001/infer/url"
payload = {
    "method_name": "gamma",
    "image_url": "https://hellorfimg.zcool.cn/provider_image/large/hi2246794331.jpg?x-image-process=image/format,webp",
}

resp = requests.post(url, json=payload, timeout=60)
print("status_code:", resp.status_code)
resp.raise_for_status()

data = resp.json()
img_bytes = base64.b64decode(data["processed_image_base64"])
with open("processed_from_url.jpg", "wb") as f:
    f.write(img_bytes)

print("saved processed_from_url.jpg")
