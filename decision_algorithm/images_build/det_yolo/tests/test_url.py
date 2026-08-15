import base64

import requests

url = "http://127.0.0.1:8000/infer/url"
payload = {
    "model_name": "anti_uav_yolov8n",
    "image_url": "https://tse1.mm.bing.net/th/id/OIP.sasNdZBX67Boyee0mvx7qAHaE8?rs=1&pid=ImgDetMain&o=7&rm=3",
}

resp = requests.post(url, json=payload, timeout=60)

print("status_code:", resp.status_code)
resp.raise_for_status()
data = resp.json()

print("num_detections:", data["num_detections"])
print("detections:", data["detections"])
print("yolo_txt:", data["yolo_txt"])

img_bytes = base64.b64decode(data["annotated_image_base64"])
with open("annotated_from_url.jpg", "wb") as handle:
    handle.write(img_bytes)

print("saved annotated_from_url.jpg")
