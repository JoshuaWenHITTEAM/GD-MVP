from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request


def request_json(url: str, method: str = "GET", payload: dict | None = None, timeout: int = 10) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"request timed out: {exc}") from exc


def pick_algorithm_uuid(api_base: str, timeout: int) -> str:
    status, data = request_json(f"{api_base}/api/v1/algorithms?pageNum=1&pageSize=10", timeout=timeout)
    if status != 200:
        raise RuntimeError(f"list algorithms failed: HTTP {status} {data}")
    items = (data.get("data") or {}).get("items") or []
    if not items:
        raise RuntimeError("no algorithms available to test against")
    return items[0]["uuid"]


def build_payload(args: argparse.Namespace) -> dict:
    image_name_parts = args.local_image_name.split(":")
    repository_name = image_name_parts[0] if image_name_parts else "demo-algorithm"
    image_tag = image_name_parts[1] if len(image_name_parts) > 1 else args.version
    return {
        "version": args.version,
        "versionName": args.version_name,
        "entrypoint": args.entrypoint,
        "sourceRevision": args.source_revision,
        "configRevision": args.config_revision,
        "changelog": args.changelog,
        "sourceType": args.source_type,
        "localImageName": args.local_image_name,
        "imagePullPolicy": args.image_pull_policy,
        "registryUrl": args.registry_url,
        "repositoryName": repository_name,
        "imageTag": image_tag,
        "imageDigest": "",
        "fullImageUri": args.local_image_name,
        "imageSize": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug POST /api/v1/algorithms/{uuid}/versions")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--algorithm-uuid", default="")
    parser.add_argument("--version", default="debug-v1")
    parser.add_argument("--version-name", default="Debug Version")
    parser.add_argument("--entrypoint", default="python main.py")
    parser.add_argument("--source-revision", default="mock-source-revision")
    parser.add_argument("--config-revision", default="mock-config-revision")
    parser.add_argument("--changelog", default="frontend debug request")
    parser.add_argument("--source-type", default="local")
    parser.add_argument("--local-image-name", default="gd-docker-preprocess:v1")
    parser.add_argument("--image-pull-policy", default="IfNotPresent")
    parser.add_argument("--registry-url", default="")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    algorithm_uuid = args.algorithm_uuid or pick_algorithm_uuid(args.api_base, args.timeout)
    payload = build_payload(args)
    url = f"{args.api_base}/api/v1/algorithms/{urllib.parse.quote(algorithm_uuid)}/versions"

    print("POST", url)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        status, data = request_json(url, method="POST", payload=payload, timeout=args.timeout)
    except RuntimeError as exc:
        print(f"\nERROR {exc}")
        return 1
    print("\nHTTP", status)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
