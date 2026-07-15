"""Config dataclasses for llama-server and llama-benchy parameters."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field, fields


@dataclass
class ServerConfig:
    model_path: str = ""
    alias: str = "bench-model"
    host: str = "127.0.0.1"
    port: int = 8090
    ctx_size: int = 8192
    n_gpu_layers: str = "999"
    flash_attn: str = "on"  # on|off|auto
    batch_size: int = 2048
    ubatch_size: int = 512
    cache_type_k: str = "q8_0"
    cache_type_v: str = "q8_0"
    parallel: int = 1
    n_cpu_moe: str = ""  # empty = omit
    threads: str = ""  # empty = omit (let llama.cpp auto-detect)
    mlock: bool = False
    no_mmap: bool = False
    jinja: bool = True
    cache_reuse: str = ""  # empty = omit
    lora_path: str = ""
    mmproj_path: str = ""
    extra_args: str = ""  # free-text escape hatch, shlex-split and appended verbatim

    def to_args(self, server_bin: str) -> list[str]:
        args: list[str] = [
            server_bin,
            "--host", self.host,
            "--port", str(self.port),
            "--model", self.model_path,
            "--alias", self.alias,
            "--ctx-size", str(self.ctx_size),
            "--n-gpu-layers", str(self.n_gpu_layers),
            "--flash-attn", self.flash_attn,
            "--batch-size", str(self.batch_size),
            "--ubatch-size", str(self.ubatch_size),
            "--cache-type-k", self.cache_type_k,
            "--cache-type-v", self.cache_type_v,
            "--parallel", str(self.parallel),
        ]
        if self.n_cpu_moe:
            args += ["--n-cpu-moe", str(self.n_cpu_moe)]
        if self.threads:
            args += ["--threads", str(self.threads)]
        if self.mlock:
            args.append("--mlock")
        if self.no_mmap:
            args.append("--no-mmap")
        args.append("--jinja" if self.jinja else "--no-jinja")
        if self.cache_reuse:
            args += ["--cache-reuse", str(self.cache_reuse)]
        if self.lora_path:
            args += ["--lora", self.lora_path]
        if self.mmproj_path:
            args += ["--mmproj", self.mmproj_path]
        if self.extra_args.strip():
            args += shlex.split(self.extra_args)
        return args

    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}/health"

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class BenchyConfig:
    pp: str = "2048"  # space-separated list, e.g. "512 2048"
    tg: str = "32"
    depth: str = "0"
    runs: int = 3
    concurrency: str = "1"
    latency_mode: str = "generation"  # api|generation|none
    enable_prefix_caching: bool = False
    no_cache: bool = False
    format: str = "md"
    extra_args: str = ""

    def to_args(self, base_url: str, model: str, benchy_bin: str) -> list[str]:
        args: list[str] = [
            benchy_bin,
            "--base-url", base_url,
            "--model", model,
            "--pp", *self.pp.split(),
            "--tg", *self.tg.split(),
            "--depth", *self.depth.split(),
            "--runs", str(self.runs),
            "--concurrency", *self.concurrency.split(),
            "--latency-mode", self.latency_mode,
            "--format", self.format,
        ]
        if self.enable_prefix_caching:
            args.append("--enable-prefix-caching")
        if self.no_cache:
            args.append("--no-cache")
        if self.extra_args.strip():
            args += shlex.split(self.extra_args)
        return args

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "BenchyConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
