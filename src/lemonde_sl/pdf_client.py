import asyncio
import json
import sys
from os import PathLike


class PdfWorkerClient:
    def __init__(self, worker_cmd: list[str] | None = None, timeout: float = 60.0):
        self.worker_cmd = [sys.executable, "-m", "lemonde_sl.pdf_worker"]
        self.timeout = timeout
        self.proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    async def _ensure_worker(self) -> None:
        if self.proc is not None and self.proc.returncode is None:
            return
        self.proc = await asyncio.create_subprocess_exec(
            *self.worker_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

    async def render_pdf(
        self, html: str, css: str, output_path: str | PathLike[str]
    ) -> tuple[bool, str | None]:
        async with self._lock:
            await self._ensure_worker()

            job = {
                "html": html,
                "css": css,
                "output": str(output_path),
            }
            line = json.dumps(job) + "\n"

            assert self.proc is not None
            assert self.proc.stdin is not None
            assert self.proc.stdout is not None

            self.proc.stdin.write(line.encode("utf-8"))
            await self.proc.stdin.drain()

            try:
                resp_line = await asyncio.wait_for(
                    self.proc.stdout.readline(),
                    timeout=self.timeout,
                )
            except TimeoutError:
                # on tue le worker et on dira que ça a échoué
                self.proc.kill()
                await self.proc.wait()
                self.proc = None
                return False, "PDF worker timeout"

            if not resp_line:
                # worker mort
                code = self.proc.returncode
                self.proc = None
                return False, f"PDF worker exited with code {code}"

            try:
                resp = json.loads(resp_line.decode("utf-8"))
            except Exception as e:
                return False, f"Invalid response from worker: {e}"

            if resp.get("status") == "ok":
                return True, None
            else:
                return False, resp.get("error", "Unknown PDF error")

    async def close(self) -> None:
        if self.proc is not None and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5.0)
            except TimeoutError:
                self.proc.kill()
        self.proc = None
