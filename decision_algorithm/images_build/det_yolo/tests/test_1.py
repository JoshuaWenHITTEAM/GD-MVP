import requests

url = "http://127.0.0.1:8000/infer/file"

with open("tests/smoke.ppm", "rb") as handle:
    files = {"image": ("smoke.ppm", handle, "image/x-portable-pixmap")}
    data = {"model_name": "anti_uav_yolov8n"}
    resp = requests.post(url, data=data, files=files, timeout=60)

print("status_code:", resp.status_code)
print("response_text:", resp.text)
