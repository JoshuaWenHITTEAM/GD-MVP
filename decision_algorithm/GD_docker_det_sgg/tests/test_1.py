import requests

url = "http://127.0.0.1:8000/infer/url"
payload = {
    "model_name": "rgb-2_yolov12n",
    "image_url": "https://hellorfimg.zcool.cn/provider_image/large/hi2246794331.jpg?x-image-process=image/format,webp"
}

resp = requests.post(url, json=payload, timeout=60)

print("status_code:", resp.status_code)
print("response_text:", resp.text)

# 先不要急着 raise
if resp.status_code == 200:
    data = resp.json()
    print(data)
else:
    print("request failed")