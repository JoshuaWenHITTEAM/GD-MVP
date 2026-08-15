from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.database import AlgorithmModel, AlgorithmVersionModel


class RuntimeManifestError(RuntimeError):
    pass


class RuntimeManifestService:
    def __init__(self) -> None:
        self.frontend_root = Path(__file__).resolve().parents[2]
        self.project_root = self.frontend_root.parent
        self.images_build_root = self.project_root / 'decision_algorithm' / 'images_build'

    def load_for_version(
        self,
        algorithm: AlgorithmModel,
        version: AlgorithmVersionModel,
    ) -> dict[str, Any]:
        bundle_path = self.discover_bundle_path(algorithm, version)
        manifest_path = bundle_path / 'runtime.manifest.json'
        if not manifest_path.exists():
            raise RuntimeManifestError(f'runtime.manifest.json not found under {bundle_path}')

        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise RuntimeManifestError(f'invalid runtime manifest JSON: {manifest_path}') from exc

        self._normalize_service_endpoints(manifest)
        manifest['bundlePath'] = str(bundle_path)
        manifest['manifestPath'] = str(manifest_path)
        self._validate_manifest(manifest)
        return manifest

    def discover_bundle_path(
        self,
        algorithm: AlgorithmModel,
        version: AlgorithmVersionModel,
    ) -> Path:
        seen: set[Path] = set()
        for candidate in self._candidate_bundle_paths(algorithm, version):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if (resolved / 'runtime.manifest.json').exists():
                return resolved

        checked = ', '.join(str(item) for item in seen) or '<none>'
        raise RuntimeManifestError(f'cannot locate runtime bundle path, checked: {checked}')

    def default_model_name(
        self,
        manifest: dict[str, Any],
    ) -> str:
        invoke = manifest.get('invoke') or {}
        url_endpoint = invoke.get('urlEndpoint') or {}
        body = url_endpoint.get('body') or {}
        model_name = body.get('model_name')
        if isinstance(model_name, str) and model_name and model_name != 'string':
            return model_name

        bundle_path = Path(manifest['bundlePath'])
        model_root = bundle_path / (manifest.get('artifacts', {}).get('modelRoot') or 'models')
        for pattern in ('*.pt', '*.pth', '*.pth.tar'):
            for file_path in sorted(model_root.glob(pattern)):
                return self._strip_model_suffix(file_path.name)

        algorithm_key = manifest.get('algorithmKey')
        if isinstance(algorithm_key, str) and algorithm_key:
            return algorithm_key
        raise RuntimeManifestError(f'cannot infer default model name from manifest: {manifest["manifestPath"]}')

    def _candidate_bundle_paths(
        self,
        algorithm: AlgorithmModel,
        version: AlgorithmVersionModel,
    ):
        search_values = [
            algorithm.codePath,
            algorithm.configPath,
        ]
        for value in search_values:
            if not value:
                continue
            raw_path = Path(value).expanduser()
            path = raw_path if raw_path.is_absolute() else (self.project_root / raw_path)
            yield from self._walk_parents(path)

        for name in self._name_candidates(algorithm, version):
            candidate = self.images_build_root / name
            if candidate.exists():
                yield candidate

    def _walk_parents(self, path: Path):
        current = path if path.is_dir() else path.parent
        while True:
            yield current
            if current == current.parent:
                break
            current = current.parent

    def _name_candidates(
        self,
        algorithm: AlgorithmModel,
        version: AlgorithmVersionModel,
    ) -> list[str]:
        raw_values = [
            algorithm.algorithmCode,
            algorithm.algorithmName,
            version.repositoryName,
            (version.localImageName or '').split(':')[0],
            Path(algorithm.codePath).parent.name if algorithm.codePath else '',
            Path(algorithm.codePath).stem if algorithm.codePath else '',
            Path(algorithm.configPath).parent.name if algorithm.configPath else '',
        ]
        candidates: list[str] = []
        for value in raw_values:
            normalized = self._normalize_name(value)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _normalize_name(self, value: str | None) -> str:
        if not value:
            return ''
        name = value.strip().replace('\\', '/').split('/')[-1]
        name = re.sub(r'\.(py|ya?ml|json|pt|pth(?:\.tar)?)$', '', name, flags=re.IGNORECASE)
        return re.sub(r'[^a-zA-Z0-9_+\-]+', '_', name).strip('_')

    def _strip_model_suffix(self, filename: str) -> str:
        for suffix in ('.pth.tar', '.pth', '.pt'):
            if filename.endswith(suffix):
                return filename[: -len(suffix)]
        return Path(filename).stem

    def _normalize_service_endpoints(self, manifest: dict[str, Any]) -> None:
        service = manifest.get('service')
        if not isinstance(service, dict):
            return
        host = service.get('host')
        host_port = service.get('hostPort')
        if host and host_port:
            service['baseUrl'] = f'http://{host}:{host_port}'

    def _validate_manifest(self, manifest: dict[str, Any]) -> None:
        required_root = ['algorithmKey', 'algorithmType', 'composeFile', 'service', 'invoke']
        for key in required_root:
            if key not in manifest:
                raise RuntimeManifestError(f'manifest missing required key: {key}')

        service = manifest['service']
        for key in ['host', 'hostPort', 'healthPath', 'readyPath']:
            if key not in service:
                raise RuntimeManifestError(f'manifest service missing required key: {key}')


runtime_manifest_service = RuntimeManifestService()
