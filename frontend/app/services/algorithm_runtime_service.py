from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import httpx


class AlgorithmRuntimeError(RuntimeError):
    pass


class AlgorithmRuntimeService:
    async def get_runtime_status(self, manifest: dict[str, Any]) -> dict[str, Any]:
        base_url = manifest['service']['baseUrl'].rstrip('/')
        health_path = manifest['service']['healthPath']
        ready_path = manifest['service']['readyPath']
        version_path = manifest['service'].get('versionPath')

        health_data: dict[str, Any] | None = None
        ready_data: dict[str, Any] | None = None
        version_data: dict[str, Any] | None = None

        async with httpx.AsyncClient(timeout=5.0) as client:
            health_response = await self._safe_get(client, f'{base_url}{health_path}')
            if health_response is not None:
                health_data = health_response
            ready_response = await self._safe_get(client, f'{base_url}{ready_path}')
            if ready_response is not None:
                ready_data = ready_response
            if version_path:
                version_response = await self._safe_get(client, f'{base_url}{version_path}')
                if version_response is not None:
                    version_data = version_response

        return {
            'bundlePath': manifest['bundlePath'],
            'baseUrl': base_url,
            'healthy': health_data is not None,
            'ready': ready_data is not None,
            'health': health_data,
            'readyInfo': ready_data,
            'versionInfo': version_data,
        }

    async def ensure_runtime_started(
        self,
        manifest: dict[str, Any],
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        status = await self.get_runtime_status(manifest)
        if status['ready'] or status['healthy']:
            return status

        try:
            await self._run_compose(manifest, 'up', '-d')
        except AlgorithmRuntimeError as exc:
            container_name = manifest.get('service', {}).get('containerName')
            if container_name and self._is_container_name_conflict(str(exc)):
                return await self._recover_conflicting_container(
                    manifest,
                    container_name,
                    timeout_seconds=timeout_seconds,
                )
            else:
                raise
        return await self.wait_until_available(manifest, timeout_seconds=timeout_seconds)

    async def stop_runtime(self, manifest: dict[str, Any]) -> dict[str, Any]:
        result = await self._run_compose(manifest, 'down')
        status = await self.get_runtime_status(manifest)
        return {
            'command': result,
            'status': status,
        }

    async def wait_until_ready(
        self,
        manifest: dict[str, Any],
        timeout_seconds: int = 60,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_status: dict[str, Any] | None = None
        while asyncio.get_running_loop().time() < deadline:
            last_status = await self.get_runtime_status(manifest)
            if last_status['ready']:
                return last_status
            await asyncio.sleep(poll_interval)
        raise AlgorithmRuntimeError(f'runtime did not become ready within {timeout_seconds}s: {last_status}')

    async def wait_until_available(
        self,
        manifest: dict[str, Any],
        timeout_seconds: int = 60,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_status: dict[str, Any] | None = None
        while asyncio.get_running_loop().time() < deadline:
            last_status = await self.get_runtime_status(manifest)
            if last_status['ready'] or last_status['healthy']:
                return last_status
            await asyncio.sleep(poll_interval)
        raise AlgorithmRuntimeError(
            f'runtime did not become healthy within {timeout_seconds}s: {last_status}'
        )

    async def _run_compose(self, manifest: dict[str, Any], *args: str) -> dict[str, Any]:
        bundle_path = Path(manifest['bundlePath'])
        compose_file = bundle_path / manifest['composeFile']
        if not compose_file.exists():
            raise AlgorithmRuntimeError(f'compose file not found: {compose_file}')

        command = ['docker', 'compose', '-f', str(compose_file), *args]
        return await self._run_command(command, cwd=bundle_path)

    async def _run_docker_command(self, *args: str) -> dict[str, Any]:
        command = ['docker', *args]
        return await self._run_command(command)

    async def _run_command(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> dict[str, Any]:
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        payload = {
            'command': command,
            'returncode': result.returncode,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
        }
        if result.returncode != 0:
            raise AlgorithmRuntimeError(f'docker command failed: {payload}')
        return payload

    def _is_container_name_conflict(self, error_message: str) -> bool:
        return 'container name' in error_message.lower() and 'already in use' in error_message.lower()

    async def _recover_conflicting_container(
        self,
        manifest: dict[str, Any],
        container_name: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        try:
            await self._run_docker_command('start', container_name)
            return await self.wait_until_available(manifest, timeout_seconds=min(timeout_seconds, 20))
        except AlgorithmRuntimeError:
            pass

        await self._run_docker_command('rm', '-f', container_name)
        await self._run_compose(manifest, 'up', '-d')
        return await self.wait_until_available(manifest, timeout_seconds=timeout_seconds)

    async def _safe_get(self, client: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


algorithm_runtime_service = AlgorithmRuntimeService()
