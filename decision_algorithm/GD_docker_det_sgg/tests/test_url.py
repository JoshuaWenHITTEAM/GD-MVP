import base64
import requests

url = "http://127.0.0.1:8000/infer/url"
payload = {
    "model_name": "rgb-2_yolov12n",
    "image_url": "https://hellorfimg.zcool.cn/provider_image/large/hi2246794331.jpg?x-image-process=image/format,webp"
}

resp = requests.post(url, json=payload, timeout=60)

print("status_code:", resp.status_code)
# print("response_text:", resp.text)

resp.raise_for_status()
data = resp.json()

print("num_detections:", data["num_detections"])
print("detections:", data["detections"])
print("yolo_txt:", data["yolo_txt"])

img_bytes = base64.b64decode(data["annotated_image_base64"])
with open("annotated_from_url.jpg", "wb") as f:
    f.write(img_bytes)

print("saved annotated_from_url.jpg")