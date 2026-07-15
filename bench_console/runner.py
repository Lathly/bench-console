"""Orchestrates: stop router -> start llama-server -> wait for health -> run llama-benchy."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from bench_console.config import BenchyConfig, ServerConfig

LogFn = Callable[[str], None]

DEFAULT_SERVER_BIN = os.path.expanduser("~/ai/llama.cpp/build/bin/llama-server")
DEFAULT_BENCHY_BIN = os.path.expanduser("~/ai/llama-benchy/.venv/bin/llama-benchy")
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
ROUTER_SERVICE = "llama.service"
READY_TIMEOUT_S = float(os.environ.get("BENCH_CONSOLE_READY_TIMEOUT", "180"))
HEALTH_POLL_INTERVAL_S = 1.0


@dataclass
class RunResult:
    success: bool
    transcript_path: Path | None = None
    error: str | None = None


class BenchRunner:
    def __init__(self, server_bin: str | None = None, benchy_bin: str | None = None):
        self.server_bin = server_bin or os.environ.get("LLAMA_SERVER_BIN", DEFAULT_SERVER_BIN)
        self.benchy_bin = benchy_bin or os.environ.get("BENCHY_BIN", DEFAULT_BENCHY_BIN)
        self._server_proc: asyncio.subprocess.Process | None = None
        self._benchy_proc: asyncio.subprocess.Process | None = None
        self._stopping = False

    async def stop(self) -> None:
        """Kill any in-flight subprocesses. Safe to call even if nothing is running."""
        self._stopping = True
        for proc in (self._benchy_proc, self._server_proc):
            if proc is not None and proc.returncode is None:
                proc.terminate()
        for proc in (self._benchy_proc, self._server_proc):
            if proc is not None and proc.returncode is None:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()

    async def run(self, preset_name: str, server: ServerConfig, benchy: BenchyConfig, log: LogFn) -> RunResult:
        self._stopping = False
        transcript: list[str] = []

        def emit(line: str) -> None:
            transcript.append(line)
            log(line)

        if not server.model_path or not Path(server.model_path).exists():
            return RunResult(False, error=f"Model not found: {server.model_path!r}")
        if not Path(self.server_bin).exists():
            return RunResult(False, error=f"llama-server binary not found: {self.server_bin}")
        if not Path(self.benchy_bin).exists():
            return RunResult(False, error=f"llama-benchy binary not found: {self.benchy_bin}")

        await self._stop_router_if_active(emit)

        server_args = server.to_args(self.server_bin)
        emit("=== llama-server params ===")
        for a in server_args:
            emit(a)
        emit("=" * 28)

        try:
            self._server_proc = await asyncio.create_subprocess_exec(
                *server_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as e:
            return RunResult(False, error=f"Failed to start llama-server: {e}")

        pump_task = asyncio.create_task(self._pump(self._server_proc.stdout, emit, prefix="[server] "))

        emit(f"--- waiting for {server.health_url()} ---")
        healthy = await self._wait_for_health(server.health_url())
        if self._stopping:
            await self._cancel_and_wait(pump_task)
            await self._save_transcript(preset_name, transcript)
            return RunResult(False, error="Stopped by user")
        if not healthy:
            emit("!!! server did not become healthy in time !!!")
            await self.stop()
            await self._cancel_and_wait(pump_task)
            path = await self._save_transcript(preset_name, transcript)
            return RunResult(False, transcript_path=path, error="Timed out waiting for /health")

        emit("--- server healthy, starting llama-benchy ---")
        benchy_args = benchy.to_args(server.base_url(), server.alias, self.benchy_bin)
        emit("=== llama-benchy params ===")
        for a in benchy_args:
            emit(a)
        emit("=" * 27)

        try:
            self._benchy_proc = await asyncio.create_subprocess_exec(
                *benchy_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as e:
            await self.stop()
            await self._cancel_and_wait(pump_task)
            path = await self._save_transcript(preset_name, transcript)
            return RunResult(False, transcript_path=path, error=f"Failed to start llama-benchy: {e}")

        await self._pump(self._benchy_proc.stdout, emit, prefix="")
        benchy_rc = await self._benchy_proc.wait()

        emit(f"--- llama-benchy exited with code {benchy_rc} ---")

        await self.stop()
        await self._cancel_and_wait(pump_task)

        path = await self._save_transcript(preset_name, transcript)
        if benchy_rc != 0:
            return RunResult(False, transcript_path=path, error=f"llama-benchy exited with code {benchy_rc}")
        return RunResult(True, transcript_path=path)

    async def _stop_router_if_active(self, emit: LogFn) -> None:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "--user", "is-active", ROUTER_SERVICE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        if out.decode().strip() == "active":
            emit(f"--- {ROUTER_SERVICE} is active, stopping it to free the GPU ---")
            stop_proc = await asyncio.create_subprocess_exec("systemctl", "--user", "stop", ROUTER_SERVICE)
            await stop_proc.wait()
            emit(f"--- {ROUTER_SERVICE} stopped (restart later with: systemctl --user start {ROUTER_SERVICE}) ---")

    async def _wait_for_health(self, url: str) -> bool:
        deadline = time.monotonic() + READY_TIMEOUT_S
        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                if self._stopping:
                    return False
                if self._server_proc is not None and self._server_proc.returncode is not None:
                    return False
                try:
                    resp = await client.get(url, timeout=2)
                    if resp.status_code == 200:
                        return True
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(HEALTH_POLL_INTERVAL_S)
        return False

    async def _cancel_and_wait(self, task: asyncio.Task) -> None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _pump(self, stream: asyncio.StreamReader | None, emit: LogFn, prefix: str) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            emit(prefix + line.decode(errors="replace").rstrip())

    async def _save_transcript(self, preset_name: str, transcript: list[str]) -> Path:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = RESULTS_DIR / f"{preset_name}_{stamp}.txt"
        path.write_text("\n".join(transcript) + "\n")
        return path
