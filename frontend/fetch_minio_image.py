from __future__ import annotations

import argparse
import sys
from pathlib import Path

from minio.error import S3Error

from app.core.config import get_settings
from app.core.minio_client import get_minio_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Download a single object from MinIO and save it locally.'
    )
    parser.add_argument('--bucket', required=True, help='MinIO bucket name')
    parser.add_argument('--object-key', required=True, help='Object key in the bucket')
    parser.add_argument(
        '--output',
        required=True,
        help='Local output file path, e.g. ./tmp/test.jpg',
    )
    parser.add_argument(
        '--show-config',
        action='store_true',
        help='Print the MinIO endpoint and exit before downloading.',
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    print(
        f'MinIO endpoint: {settings.minio_endpoint} '
        f'(secure={settings.minio_secure})'
    )

    if args.show_config:
        return 0

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    minio_service = get_minio_service()
    response = None
    try:
        response = minio_service.get_object_stream(args.bucket, args.object_key)
        with output_path.open('wb') as f:
            for chunk in response.stream(32 * 1024):
                if chunk:
                    f.write(chunk)
    except S3Error as exc:
        print(f'MinIO request failed: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        print(f'Unexpected error: {exc}', file=sys.stderr)
        return 1
    finally:
        if response is not None:
            response.close()
            response.release_conn()

    print(f'Downloaded to: {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
