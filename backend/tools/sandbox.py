import asyncio
import time
from typing import Optional

DOCKER_AVAILABLE = False
docker = None

try:
    import docker as docker_module

    docker = docker_module
    DOCKER_AVAILABLE = True
except ImportError:
    pass


class CodeSandbox:
    DEFAULT_IMAGE = "python:3.11-slim"
    CPU_LIMIT = 1.0
    MEMORY_LIMIT = "256m"
    TIMEOUT = 30
    MAX_TIMEOUT = 60
    MAX_OUTPUT = 10000
    NETWORK_DISABLED = True

    LANGUAGE_IMAGES = {
        "python": ("python:3.11-slim", ["python", "-c"]),
        "javascript": ("node:20-slim", ["node", "-e"]),
        "bash": ("bash:5", ["bash", "-c"]),
    }

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if not DOCKER_AVAILABLE:
            raise RuntimeError(
                "Docker SDK not installed. Install with: pip install docker"
            )
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[int] = None,
        memory_limit: Optional[str] = None,
        network_enabled: bool = False,
    ) -> dict:
        if not DOCKER_AVAILABLE:
            return {
                "success": False,
                "error": "Docker SDK not installed. Install with: pip install docker",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": 0.0,
            }

        effective_timeout = min(timeout or self.TIMEOUT, self.MAX_TIMEOUT)
        effective_memory = memory_limit or self.MEMORY_LIMIT

        image, command_prefix = self._get_image_and_command(language)
        command = command_prefix + [code]

        try:
            result = await asyncio.to_thread(
                self._run_container,
                image=image,
                command=command,
                timeout=effective_timeout,
                memory_limit=effective_memory,
                network_enabled=network_enabled,
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": 0.0,
            }

    def _get_image_and_command(self, language: str) -> tuple:
        return self.LANGUAGE_IMAGES.get(
            language.lower(), self.LANGUAGE_IMAGES["python"]
        )

    def _run_container(
        self,
        image: str,
        command: list,
        timeout: int,
        memory_limit: str,
        network_enabled: bool,
    ) -> dict:
        start_time = time.time()

        try:
            self.client.images.get(image)
        except Exception:
            try:
                self.client.images.pull(image)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to pull image {image}: {e}",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "execution_time": time.time() - start_time,
                }

        container = None
        try:
            container = self.client.containers.run(
                image,
                command,
                detach=True,
                network_disabled=not network_enabled,
                mem_limit=memory_limit,
                cpu_quota=int(self.CPU_LIMIT * 100000),
                security_opt=["no-new-privileges"],
                user="nobody",
                read_only=True,
                tmpfs={"/tmp": "size=10m,exec"},
                working_dir="/tmp",
            )

            try:
                result = container.wait(timeout=timeout)
                stdout = container.logs(stdout=True, stderr=False).decode(
                    "utf-8", errors="replace"
                )
                stderr = container.logs(stdout=False, stderr=True).decode(
                    "utf-8", errors="replace"
                )
                exit_code = result.get("StatusCode", -1)
                success = exit_code == 0
            except Exception as e:
                stdout = ""
                stderr = f"Timeout or error: {e}"
                exit_code = -1
                success = False

            return {
                "success": success,
                "stdout": stdout[: self.MAX_OUTPUT],
                "stderr": stderr[: self.MAX_OUTPUT],
                "exit_code": exit_code,
                "execution_time": time.time() - start_time,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "execution_time": time.time() - start_time,
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
