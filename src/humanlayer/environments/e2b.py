"""E2B sandbox environment adapted from Harbor.

This is an async implementation - all methods that interact with the sandbox
are async and must be awaited. The caller is responsible for managing the
event loop (e.g., using asyncio.run() at the top level).
"""

import os
from pathlib import Path
from typing import Any

from dirhash import dirhash
from dockerfile_parse import DockerfileParser
from e2b import AsyncSandbox, AsyncTemplate, Template
from e2b.sandbox.filesystem.filesystem import WriteEntry
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


class E2BEnvironmentConfig(BaseModel):
    environment_dir: Path
    environment_name: str
    timeout: int = 86400
    env: dict[str, str] = {}
    allow_internet: bool = True
    session_id: str = "default"
    docker_image: str | None = None
    jobs_dir: str = "examples/jobs"


class E2BEnvironment:
    """Async E2B sandbox environment.

    Usage:
        env = E2BEnvironment(environment_dir=..., environment_name=...)
        await env.start()
        result = await env.execute("ls -la")
        await env.stop()
    """
    _UPLOAD_BATCH_SIZE = 20

    def __init__(self, *, config_class: type = E2BEnvironmentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self._sandbox: AsyncSandbox | None = None
        self.config.environment_dir = self.config.environment_dir.absolute()

        # Extract WORKDIR from Dockerfile if available
        try:
            self._work_dir = next(
                (
                    instruction["value"]
                    for instruction in reversed(
                        DockerfileParser(path=str(self.config.environment_dir / "Dockerfile")).structure
                    )
                    if instruction.get("instruction") == "WORKDIR"
                ),
                "/home/user",
            )
        except:
            raise ValueError("WORKDIR not found in Dockerfile")

        self.user_signature = os.getenv("E2B_USER_SIGNATURE", "")
        if self.user_signature == "":
            raise ValueError("E2B_USER_SIGNATURE is not set")
        self._template_name = f"{self.config.environment_name}__{self.user_signature}__{dirhash(self.config.environment_dir, 'sha256')[:8]}".replace(".", "-")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def _create_template(self):
        if self.config.docker_image:
            template = Template().from_image(image=self.config.docker_image)
        else:
            # E2B resolves COPY paths relative to cwd, so must be in environment dir
            old_cwd = os.getcwd()
            try:
                os.chdir(self.config.environment_dir)
                template = Template().from_dockerfile(dockerfile_content_or_path="Dockerfile")
            finally:
                os.chdir(old_cwd)

        await AsyncTemplate.build(template=template, alias=self._template_name, cpu_count=4, memory_mb=4096)

    async def _does_template_exist(self) -> bool:
        try:
            return await AsyncTemplate.exists(alias=self._template_name)
        except:
            return False

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def _create_sandbox(self):
        """Create the sandbox instance."""
        metadata = {
            "environment_name": self.config.environment_name,
            "session_id": self.config.session_id,
        }
        self._sandbox = await AsyncSandbox.create(
            template=self._template_name,
            metadata=metadata,
            timeout=self.config.timeout,
            allow_internet_access=self.config.allow_internet,
        )

    async def start(self, force_build: bool = False):
        """Start the sandbox environment.

        Args:
            force_build: If True, rebuild the template even if it exists.
        """
        if force_build or not await self._does_template_exist():
            await self._create_template()

        await self._create_sandbox()

        if not self._sandbox:
            raise RuntimeError("Sandbox not found but was just created.")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        """Execute a command in the sandbox.

        Args:
            command: The command to execute.
            cwd: Working directory for the command.
            timeout: Timeout in seconds (0 for no timeout).

        Returns:
            Dict with 'output' and 'returncode' keys.
        """
        if not self._sandbox:
            raise RuntimeError("Sandbox not started. Call start() first.")

        handle = await self._sandbox.commands.run(
            cmd=command,
            background=True,
            cwd=cwd or self._work_dir,
            envs=self.config.env,
            timeout=timeout or 0,
            user="root",
        )
        result = await handle.wait()

        output = result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr

        return {"output": output, "returncode": result.exit_code}

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def upload_file(self, source_path: Path | str, target_path: str):
        """Upload a file to the sandbox.

        Args:
            source_path: Local path to the file.
            target_path: Path in the sandbox.
        """
        if not self._sandbox:
            raise RuntimeError("Sandbox not started. Call start() first.")
        await self._sandbox.files.write(target_path, Path(source_path).read_bytes())

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def upload_dir(self, source_dir: Path | str, target_dir: str):
        """Upload a directory to the sandbox.

        Args:
            source_dir: Local directory path.
            target_dir: Path in the sandbox.
        """
        if not self._sandbox:
            raise RuntimeError("Sandbox not started. Call start() first.")

        files = []
        for file_path in Path(source_dir).rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(Path(source_dir))
                files.append(WriteEntry(path=str(Path(target_dir) / rel_path), data=file_path.read_bytes()))

        for i in range(0, len(files), self._UPLOAD_BATCH_SIZE):
            batch = files[i:i + self._UPLOAD_BATCH_SIZE]
            await self._sandbox.files.write_files(batch)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def download_file(self, source_path: str, target_path: Path | str):
        """Download a file from the sandbox.

        Args:
            source_path: Path in the sandbox.
            target_path: Local path to save the file.
        """
        if not self._sandbox:
            raise RuntimeError("Sandbox not started. Call start() first.")
        content = await self._sandbox.files.read(source_path, format="bytes")
        Path(target_path).write_bytes(content)

    def get_template_vars(self) -> dict[str, Any]:
        """Get template variables for prompt rendering."""
        return self.config.model_dump()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def _stop_sandbox(self):
        """Internal method to stop the sandbox with retry."""
        if self._sandbox:
            await self._sandbox.kill()

    async def stop(self, delete: bool = True):
        """Stop the sandbox environment.

        Args:
            delete: Ignored - E2B sandboxes are always deleted after use.
        """
        if self._sandbox:
            try:
                await self._stop_sandbox()
            except Exception as e:
                print(f"Error stopping sandbox: {e}")
            finally:
                self._sandbox = None
