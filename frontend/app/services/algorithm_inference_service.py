from __future__ import annotations

import json
import mimetypes
import re
import uuid as py_uuid
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.database import AlgorithmModel, AlgorithmVersionModel, MediaAsset
from app.services.asset_service import asset_service
from app.services.algorithm_runtime_service import AlgorithmRuntimeError, algorithm_runtime_service
from app.services.runtime_manifest_service import RuntimeManifestError, runtime_manifest_service

settings = get_settings()


class AlgorithmInferenceService:
    def normalize_algorithm_type(self, value: str | None) -> str:
        mapping = {
            'detect': 'detection',
            'detection': 'detection',
            'tracking': 'tracking',
            'track': 'tracking',
            'preprocessing': 'preprocessing',
        }
        return mapping.get((value or '').strip().lower(), (value or '').strip().lower())

    async def list_vision_algorithms(self, db: Session) -> list[dict[str, Any]]:
        versions = (
            db.query(AlgorithmVersionModel, AlgorithmModel)
            .join(AlgorithmModel, AlgorithmVersionModel.algorithmUuid == AlgorithmModel.uuid)
            .filter(AlgorithmVersionModel.is_deleted.is_(False))
            .order_by(AlgorithmModel.updatedAt.desc(), AlgorithmVersionModel.updatedAt.desc())
            .all()
        )

        items: list[dict[str, Any]] = []
        for version, algorithm in versions:
            items.append({
                'algorithmUuid': algorithm.uuid,
                'algorithmCode': algorithm.algorithmCode,
                'algorithmName': algorithm.algorithmName,
                'algorithmType': self.normalize_algorithm_type(algorithm.algorithmType),
                'versionUuid': version.uuid,
                'version': version.version,
                'versionName': version.versionName,
                'publishStatus': version.publishStatus,
            })
        return items

    async def start_runtime_for_version(self, db: Session, version_uuid: str) -> dict[str, Any]:
        version, algorithm = self._get_version_and_algorithm(db, version_uuid)
        manifest = self._load_manifest_or_raise(algorithm, version)
        status = await self._ensure_runtime_started_or_raise(manifest)
        return {
            'versionUuid': version.uuid,
            'algorithmUuid': algorithm.uuid,
            'baseUrl': manifest['service']['baseUrl'],
            'status': status,
        }

    async def stop_runtime_for_version(self, db: Session, version_uuid: str) -> dict[str, Any]:
        version, algorithm = self._get_version_and_algorithm(db, version_uuid)
        manifest = self._load_manifest_or_raise(algorithm, version)
        try:
            result = await algorithm_runtime_service.stop_runtime(manifest)
        except AlgorithmRuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            'versionUuid': version.uuid,
            'algorithmUuid': algorithm.uuid,
            'baseUrl': manifest['service']['baseUrl'],
            **result,
        }

    async def get_runtime_status_for_version(self, db: Session, version_uuid: str) -> dict[str, Any]:
        version, algorithm = self._get_version_and_algorithm(db, version_uuid)
        manifest = self._load_manifest_or_raise(algorithm, version)
        status = await algorithm_runtime_service.get_runtime_status(manifest)
        return {
            'versionUuid': version.uuid,
            'algorithmUuid': algorithm.uuid,
            'baseUrl': manifest['service']['baseUrl'],
            'status': status,
        }

    async def run_inference(
        self,
        db: Session,
        pg_db: Session,
        version_uuid: str,
        asset_uuid: str | None = None,
        asset_uuids: list[str] | None = None,
        template_bbox: list[int] | None = None,
    ) -> dict[str, Any]:
        version, algorithm = self._get_version_and_algorithm(db, version_uuid)
        manifest = self._load_manifest_or_raise(algorithm, version)
        await self._ensure_runtime_started_or_raise(manifest)

        algorithm_type = self.normalize_algorithm_type(algorithm.algorithmType)
        if algorithm_type == 'tracking':
            return await self._run_tracking(pg_db, manifest, version, asset_uuids, template_bbox)
        if algorithm_type == 'preprocessing':
            return await self._run_preprocessing(pg_db, manifest, version, asset_uuid)
        return await self._run_detection(pg_db, manifest, version, asset_uuid)

    async def stream_tracking_inference(
        self,
        db: Session,
        pg_db: Session,
        version_uuid: str,
        asset_uuids: list[str] | None = None,
        template_bbox: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        version, algorithm = self._get_version_and_algorithm(db, version_uuid)
        manifest = self._load_manifest_or_raise(algorithm, version)
        await self._ensure_runtime_started_or_raise(manifest)
        async for event in self._stream_tracking(pg_db, manifest, version, asset_uuids, template_bbox):
            yield event

    def _get_version_and_algorithm(
        self,
        db: Session,
        version_uuid: str,
    ) -> tuple[AlgorithmVersionModel, AlgorithmModel]:
        version = db.query(AlgorithmVersionModel).filter(
            AlgorithmVersionModel.uuid == version_uuid,
            AlgorithmVersionModel.is_deleted.is_(False),
        ).first()
        if not version:
            raise HTTPException(status_code=404, detail='算法版本不存在')

        algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.uuid == version.algorithmUuid).first()
        if not algorithm:
            raise HTTPException(status_code=404, detail='算法不存在')
        return version, algorithm

    def _load_manifest_or_raise(
        self,
        algorithm: AlgorithmModel,
        version: AlgorithmVersionModel,
    ) -> dict[str, Any]:
        try:
            return runtime_manifest_service.load_for_version(algorithm, version)
        except RuntimeManifestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def _ensure_runtime_started_or_raise(self, manifest: dict[str, Any]) -> dict[str, Any]:
        try:
            return await algorithm_runtime_service.ensure_runtime_started(manifest)
        except AlgorithmRuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _get_asset(self, pg_db: Session, asset_uuid: str) -> MediaAsset:
        try:
            parsed_uuid = py_uuid.UUID(asset_uuid)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f'无效资产 UUID: {asset_uuid}') from exc

        asset = pg_db.query(MediaAsset).filter(MediaAsset.uuid == parsed_uuid).first()
        if not asset:
            raise HTTPException(status_code=404, detail=f'资产不存在: {asset_uuid}')
        return asset

    def _build_asset_url(self, asset: MediaAsset) -> str:
        return asset_service.minio_service.presigned_get_url(
            asset.bucket_name,
            asset.object_key,
            expires_seconds=1800,
        )

    def _read_asset_bytes(self, asset: MediaAsset) -> bytes:
        response = asset_service.minio_service.get_object_stream(
            asset.bucket_name,
            asset.object_key,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def _run_detection(
        self,
        pg_db: Session,
        manifest: dict[str, Any],
        version: AlgorithmVersionModel,
        asset_uuid: str | None,
    ) -> dict[str, Any]:
        if not asset_uuid:
            raise HTTPException(status_code=400, detail='检测算法推理需要 asset_uuid')

        asset = self._get_asset(pg_db, asset_uuid)
        invoke = manifest['invoke']
        model_name = runtime_manifest_service.default_model_name(manifest)
        base_url = manifest['service']['baseUrl'].rstrip('/')
        file_endpoint = invoke.get('fileEndpoint')
        if file_endpoint:
            object_name = Path(asset.object_key).name or f'{asset_uuid}.bin'
            content_type = mimetypes.guess_type(object_name)[0] or 'application/octet-stream'
            image_bytes = self._read_asset_bytes(asset)
            response_data = await self._post_multipart(
                base_url + file_endpoint['path'],
                data={
                    'model_name': model_name,
                    'return_image': 'true',
                    'return_yolo_txt': 'true',
                },
                files={
                    'image': (object_name, image_bytes, content_type),
                },
            )
        else:
            asset_url = self._build_asset_url(asset)
            url_endpoint = invoke['urlEndpoint']
            request_payload = {
                'model_name': model_name,
                'image_url': asset_url,
                'return_image': True,
                'return_yolo_txt': True,
            }
            response_data = await self._post_json(
                base_url + url_endpoint['path'],
                request_payload,
            )
        return {
            'mode': 'detection',
            'version_uuid': version.uuid,
            'asset_uuid': asset_uuid,
            'runtime_base_url': manifest['service']['baseUrl'],
            'runtime_result': response_data,
        }

    async def _run_tracking(
        self,
        pg_db: Session,
        manifest: dict[str, Any],
        version: AlgorithmVersionModel,
        asset_uuids: list[str] | None,
        template_bbox: list[int] | None,
    ) -> dict[str, Any]:
        init_result = None
        track_results: list[dict[str, Any]] = []
        template_asset_uuid = None
        resolved_template_bbox = template_bbox
        async for event in self._stream_tracking(pg_db, manifest, version, asset_uuids, template_bbox):
            if event['event'] == 'init':
                init_result = event['init_result']
                template_asset_uuid = event['template_asset_uuid']
                resolved_template_bbox = event['template_bbox']
            elif event['event'] == 'frame':
                track_results.append({
                    'asset_uuid': event['asset_uuid'],
                    'frame_index': event['frame_index'],
                    'runtime_result': event['runtime_result'],
                })
        return {
            'mode': 'tracking',
            'version_uuid': version.uuid,
            'runtime_base_url': manifest['service']['baseUrl'],
            'template_asset_uuid': template_asset_uuid,
            'template_bbox': resolved_template_bbox,
            'init_result': init_result,
            'track_results': track_results,
        }

    async def _stream_tracking(
        self,
        pg_db: Session,
        manifest: dict[str, Any],
        version: AlgorithmVersionModel,
        asset_uuids: list[str] | None,
        template_bbox: list[int] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        if not asset_uuids or len(asset_uuids) < 2:
            raise HTTPException(status_code=400, detail='跟踪算法推理至少需要 2 帧资产')

        assets = [self._get_asset(pg_db, item) for item in asset_uuids]
        if not template_bbox:
            template_bbox = self._resolve_tracking_template_bbox(assets[0])
        if not template_bbox or len(template_bbox) != 4:
            raise HTTPException(status_code=400, detail='无法从 raw-annotations 自动匹配跟踪初始化框')
        base_url = manifest['service']['baseUrl'].rstrip('/')
        invoke = manifest['invoke']

        if invoke.get('resetTemplatePath'):
            await self._post_json(base_url + invoke['resetTemplatePath'], {})

        init_step = next(step for step in invoke['workflow'] if step['step'] == 'init')
        track_step = next(step for step in invoke['workflow'] if step['step'] == 'track')
        init_file_path = self._file_endpoint_from_workflow_path(init_step['path'])
        track_file_path = self._file_endpoint_from_workflow_path(track_step['path'])

        init_object_name = Path(assets[0].object_key).name or f'{assets[0].uuid}.bin'
        init_content_type = mimetypes.guess_type(init_object_name)[0] or 'application/octet-stream'
        init_result = await self._post_multipart(
            base_url + init_file_path,
            data={
                'x1': str(template_bbox[0]),
                'y1': str(template_bbox[1]),
                'x2': str(template_bbox[2]),
                'y2': str(template_bbox[3]),
                'return_image': 'true',
            },
            files={
                'image': (init_object_name, self._read_asset_bytes(assets[0]), init_content_type),
            },
        )
        yield {
            'event': 'init',
            'mode': 'tracking',
            'version_uuid': version.uuid,
            'runtime_base_url': manifest['service']['baseUrl'],
            'template_asset_uuid': str(assets[0].uuid),
            'template_bbox': template_bbox,
            'init_result': init_result,
        }

        for index, asset in enumerate(assets[1:], start=1):
            object_name = Path(asset.object_key).name or f'{asset.uuid}.bin'
            content_type = mimetypes.guess_type(object_name)[0] or 'application/octet-stream'
            track_result = await self._post_multipart(
                base_url + track_file_path,
                data={
                    'return_image': 'true',
                },
                files={
                    'image': (object_name, self._read_asset_bytes(asset), content_type),
                },
            )
            yield {
                'event': 'frame',
                'mode': 'tracking',
                'asset_uuid': str(asset.uuid),
                'frame_index': index,
                'runtime_result': track_result,
            }

        yield {
            'event': 'done',
            'mode': 'tracking',
            'frame_count': len(assets),
        }

    def _file_endpoint_from_workflow_path(self, path: str) -> str:
        normalized = (path or '').strip()
        if not normalized:
            raise HTTPException(status_code=500, detail='跟踪算法 manifest 缺少 workflow path')
        if normalized.endswith('/url'):
            return normalized[:-4] + '/file'
        return normalized

    def _resolve_tracking_template_bbox(self, asset: MediaAsset) -> list[int]:
        object_key = (asset.object_key or '').strip('/')
        object_parts = object_key.split('/')
        if len(object_parts) < 3:
            raise HTTPException(status_code=400, detail=f'无法从 object_key 推断序列信息: {object_key}')

        dataset_name = object_parts[0]
        sequence_name = (asset.sequence_name or object_parts[1] or '').strip()
        frame_name = Path(object_key).name
        stem_name = Path(frame_name).stem
        sequence_token = sequence_name.zfill(2) if sequence_name.isdigit() else sequence_name
        exact_first_gt_key = f'{dataset_name}/{sequence_name}/{sequence_token}_gt_first.txt'

        bbox = self._try_load_bbox_from_annotation_object(
            exact_first_gt_key,
            frame_name,
            stem_name,
            assume_xywh=True,
        )
        if bbox:
            return bbox

        candidate_prefixes = [
            f'{dataset_name}/{sequence_name}',
            sequence_name,
        ]
        candidate_object_keys = [
            f'{dataset_name}/{sequence_name}/{sequence_name}_gt_first.txt',
            f'{dataset_name}/{sequence_name}/{sequence_token}_gt.txt',
            f'{dataset_name}/{sequence_name}/IR_label.json',
            f'{dataset_name}/{sequence_name}/label.json',
            f'{dataset_name}/{sequence_name}/groundtruth.txt',
            f'{dataset_name}/{sequence_name}/groundtruth_rect.txt',
            f'{dataset_name}/{sequence_name}/{sequence_name}_gt.txt',
            f'{dataset_name}/{sequence_name}.txt',
            f'{dataset_name}/{sequence_name}.json',
        ]

        tested_keys: list[str] = []
        tested_keys.append(exact_first_gt_key)
        for candidate_key in candidate_object_keys:
            bbox = self._try_load_bbox_from_annotation_object(candidate_key, frame_name, stem_name)
            tested_keys.append(candidate_key)
            if bbox:
                return bbox

        for prefix in candidate_prefixes:
            for obj in asset_service.minio_service.list_objects(settings.raw_annotations_bucket, prefix=prefix, recursive=True):
                anno_key = getattr(obj, 'object_name', '') or ''
                if not anno_key or anno_key.endswith('/'):
                    continue
                bbox = self._try_load_bbox_from_annotation_object(anno_key, frame_name, stem_name)
                tested_keys.append(anno_key)
                if bbox:
                    return bbox

        raise HTTPException(
            status_code=404,
            detail=f'raw-annotations 中未找到 {sequence_name}/{frame_name} 对应的初始化框；已检查 {len(tested_keys)} 个标注对象',
        )

    def _try_load_bbox_from_annotation_object(
        self,
        object_key: str,
        frame_name: str,
        stem_name: str,
        assume_xywh: bool = False,
    ) -> list[int] | None:
        suffix = Path(object_key).suffix.lower()
        if suffix not in {'.json', '.txt'}:
            return None

        try:
            response = asset_service.minio_service.get_object_stream(settings.raw_annotations_bucket, object_key)
            try:
                raw_bytes = response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception:
            return None

        try:
            text = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = raw_bytes.decode('utf-8', errors='ignore')

        if suffix == '.json':
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return None
            return self._extract_bbox_from_json_payload(payload, frame_name, stem_name)

        return self._extract_bbox_from_txt_payload(text, frame_name, stem_name, assume_xywh=assume_xywh)

    def _extract_bbox_from_json_payload(
        self,
        payload: Any,
        frame_name: str,
        stem_name: str,
    ) -> list[int] | None:
        if isinstance(payload, dict):
            for key in (frame_name, stem_name):
                if key in payload:
                    return self._normalize_bbox(payload[key], assume_xywh=True)

            if isinstance(payload.get('gt_rect'), list) and payload['gt_rect']:
                return self._normalize_bbox(payload['gt_rect'][0], assume_xywh=True)
            if isinstance(payload.get('gt_bbox'), list) and payload['gt_bbox']:
                return self._normalize_bbox(payload['gt_bbox'][0], assume_xywh=True)
            if isinstance(payload.get('bbox'), (list, dict)):
                return self._normalize_bbox(payload['bbox'])
            if isinstance(payload.get('frames'), list):
                for item in payload['frames']:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get('frame') or item.get('image') or item.get('name') or '')
                    if name in {frame_name, stem_name, f'{stem_name}.jpg', f'{stem_name}.png'}:
                        return self._normalize_bbox(item.get('bbox_xyxy')) or self._normalize_bbox(item.get('bbox') or item.get('rect'), assume_xywh=True)
            return None

        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, (list, dict)):
                return self._normalize_bbox(first, assume_xywh=True)
        return None

    def _extract_bbox_from_txt_payload(
        self,
        text: str,
        frame_name: str,
        stem_name: str,
        assume_xywh: bool = False,
    ) -> list[int] | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None

        numbered_candidates = {
            frame_name,
            stem_name,
            stem_name.lstrip('0') or '0',
        }
        for line in lines:
            parts = [part.strip() for part in re.split(r'[\s,]+', line) if part.strip()]
            if len(parts) >= 5 and parts[0] in numbered_candidates:
                return self._normalize_bbox(parts[1:5], assume_xywh=True)

        parts = [part.strip() for part in re.split(r'[\s,]+', lines[0]) if part.strip()]
        return self._normalize_bbox(parts, assume_xywh=assume_xywh)

    def _normalize_bbox(self, raw_bbox: Any, assume_xywh: bool = False) -> list[int] | None:
        if raw_bbox is None:
            return None
        if isinstance(raw_bbox, dict):
            if {'x1', 'y1', 'x2', 'y2'}.issubset(raw_bbox):
                values = [raw_bbox['x1'], raw_bbox['y1'], raw_bbox['x2'], raw_bbox['y2']]
                return [int(round(float(item))) for item in values]
            if {'x', 'y', 'w', 'h'}.issubset(raw_bbox):
                x, y, w, h = [float(raw_bbox[key]) for key in ('x', 'y', 'w', 'h')]
                return [int(round(x)), int(round(y)), int(round(x + w)), int(round(y + h))]
            if 'bbox' in raw_bbox:
                return self._normalize_bbox(raw_bbox['bbox'], assume_xywh=assume_xywh)
            return None

        if isinstance(raw_bbox, (list, tuple)):
            flat = list(raw_bbox)
        else:
            flat = [item.strip() for item in str(raw_bbox).replace('[', '').replace(']', '').split(',') if item.strip()]

        if len(flat) < 4:
            return None
        try:
            nums = [float(flat[i]) for i in range(4)]
        except (TypeError, ValueError):
            return None

        x1, y1, third, fourth = nums
        if assume_xywh:
            w = max(third, 0.0)
            h = max(fourth, 0.0)
            return [int(round(x1)), int(round(y1)), int(round(x1 + w)), int(round(y1 + h))]

        return [int(round(x1)), int(round(y1)), int(round(third)), int(round(fourth))]

    async def _run_preprocessing(
        self,
        pg_db: Session,
        manifest: dict[str, Any],
        version: AlgorithmVersionModel,
        asset_uuid: str | None,
    ) -> dict[str, Any]:
        if not asset_uuid:
            raise HTTPException(status_code=400, detail='预处理算法推理需要 asset_uuid')

        asset = self._get_asset(pg_db, asset_uuid)
        invoke = manifest['invoke']
        model_name = runtime_manifest_service.default_model_name(manifest)
        base_url = manifest['service']['baseUrl'].rstrip('/')
        file_endpoint = invoke.get('fileEndpoint')
        if file_endpoint:
            object_name = Path(asset.object_key).name or f'{asset_uuid}.bin'
            content_type = mimetypes.guess_type(object_name)[0] or 'application/octet-stream'
            image_bytes = self._read_asset_bytes(asset)
            response_data = await self._post_multipart(
                base_url + file_endpoint['path'],
                data={
                    'model_name': model_name,
                    'return_image': 'true',
                },
                files={
                    'image': (object_name, image_bytes, content_type),
                },
            )
        else:
            asset_url = self._build_asset_url(asset)
            url_endpoint = invoke['urlEndpoint']
            request_payload = {
                'model_name': model_name,
                'image_url': asset_url,
                'return_image': True,
            }
            response_data = await self._post_json(
                base_url + url_endpoint['path'],
                request_payload,
            )
        return {
            'mode': 'preprocessing',
            'version_uuid': version.uuid,
            'asset_uuid': asset_uuid,
            'runtime_base_url': manifest['service']['baseUrl'],
            'runtime_result': response_data,
        }

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise HTTPException(
                status_code=502,
                detail=f'算法容器返回错误 {exc.response.status_code}: {detail}',
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f'调用算法容器失败: {exc}') from exc

    async def _post_multipart(
        self,
        url: str,
        data: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise HTTPException(
                status_code=502,
                detail=f'算法容器返回错误 {exc.response.status_code}: {detail}',
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f'调用算法容器失败: {exc}') from exc


algorithm_inference_service = AlgorithmInferenceService()
