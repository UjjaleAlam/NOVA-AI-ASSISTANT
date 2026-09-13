"""
Offline Intelligence - Phase 13
Local LLM management, optimization, and model orchestration.
Fully local, no cloud dependencies.
"""

import ollama
import json
import os
import time
import subprocess
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum


class ModelStatus(Enum):
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    UPDATING = "updating"
    REMOVING = "removing"
    ERROR = "error"
    NOT_FOUND = "not_found"


@dataclass
class ModelInfo:
    name: str
    size: str
    modified: str
    digest: str
    status: ModelStatus = ModelStatus.AVAILABLE
    quantization: str = ""
    parameters: str = ""
    family: str = ""
    description: str = ""


@dataclass
class InferenceConfig:
    model: str
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    num_predict: int = 2048
    num_ctx: int = 4096
    num_batch: int = 512
    num_gpu: int = -1  # -1 = all layers
    num_thread: int = 0  # 0 = auto
    repeat_penalty: float = 1.1
    seed: int = -1
    stop: List[str] = None


class ModelManager:
    """Manage local Ollama models."""

    def __init__(self):
        self.cache = {}
        self.cache_time = 0
        self.cache_ttl = 30  # seconds

    def list_models(self, force_refresh: bool = False) -> List[ModelInfo]:
        """List all available models with detailed info."""
        now = time.time()
        if not force_refresh and self.cache and (now - self.cache_time) < self.cache_ttl:
            return self.cache

        try:
            result = ollama.list()
            models = []

            for m in result.get("models", []):
                # Handle both dict and object formats
                if hasattr(m, 'model'):
                    # Object format (new ollama library)
                    name = m.model
                    size = m.size
                    modified = m.modified_at.isoformat() if hasattr(m, 'modified_at') and m.modified_at else ""
                    digest = m.digest[:12] if hasattr(m, 'digest') and m.digest else ""
                    
                    # Get details from ModelDetails
                    quant = ""
                    params = ""
                    family = ""
                    if hasattr(m, 'details') and m.details:
                        if hasattr(m.details, 'quantization_level'):
                            quant = m.details.quantization_level
                        if hasattr(m.details, 'parameter_size'):
                            params = m.details.parameter_size
                        if hasattr(m.details, 'family'):
                            family = m.details.family
                elif isinstance(m, dict):
                    # Dict format (old)
                    name = m.get("name", "")
                    size = m.get("size", 0)
                    modified = m.get("modified", "")
                    digest = m.get("digest", "")[:12]
                    quant = ""
                    params = ""
                    family = ""
                    if ":" in name:
                        tag = name.split(":")[-1]
                        for q in ["q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s", "q6_k", "q8_0", "f16", "f32"]:
                            if q in tag:
                                quant = q
                                break
                        for p in ["0.5b", "1b", "1.5b", "2b", "3b", "7b", "8b", "13b", "14b", "32b", "34b", "70b", "72b"]:
                            if p in tag:
                                params = p
                                break
                else:
                    continue

                model = ModelInfo(
                    name=name,
                    size=self._format_size(size),
                    modified=modified,
                    digest=digest,
                    quantization=quant,
                    parameters=params,
                    family=family
                )
                models.append(model)

            self.cache = models
            self.cache_time = now
            return models

        except Exception as e:
            return [ModelInfo(name="error", size="0", modified="", digest="", status=ModelStatus.ERROR, description=str(e))]

    def _format_size(self, bytes_val: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} PB"

    def get_model_details(self, name: str) -> Optional[Dict]:
        """Get detailed info about a specific model."""
        try:
            result = ollama.show(name)
            return result
        except Exception:
            return None

    def pull_model(self, name: str, progress_callback=None) -> bool:
        """Pull/download a model."""
        try:
            if progress_callback:
                progress_callback(ModelStatus.DOWNLOADING, f"Starting pull: {name}")

            # Use ollama pull with streaming
            for progress in ollama.pull(name, stream=True):
                if progress_callback:
                    status = progress.get("status", "")
                    completed = progress.get("completed", 0)
                    total = progress.get("total", 0)
                    if total > 0:
                        pct = (completed / total) * 100
                        progress_callback(ModelStatus.DOWNLOADING, f"{status}: {pct:.1f}%")
                    else:
                        progress_callback(ModelStatus.DOWNLOADING, status)

            self.cache = {}  # Invalidate cache
            if progress_callback:
                progress_callback(ModelStatus.AVAILABLE, f"Completed: {name}")
            return True
        except Exception as e:
            if progress_callback:
                progress_callback(ModelStatus.ERROR, f"Failed: {e}")
            return False

    def remove_model(self, name: str) -> bool:
        """Remove a model."""
        try:
            ollama.delete(name)
            self.cache = {}
            return True
        except Exception:
            return False

    def copy_model(self, source: str, destination: str) -> bool:
        """Copy/rename a model."""
        try:
            ollama.copy(source, destination)
            self.cache = {}
            return True
        except Exception:
            return False


class InferenceEngine:
    """Optimized inference engine with config management."""

    def __init__(self):
        self.default_config = InferenceConfig(model="qwen3:8b")
        self.current_config = self.default_config
        self.performance_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_time": 0.0,
            "avg_tokens_per_sec": 0.0
        }

    def set_config(self, config: InferenceConfig):
        self.current_config = config

    def get_config(self) -> InferenceConfig:
        return self.current_config

    def chat(self, messages: List[Dict], config: InferenceConfig = None) -> Dict:
        """Run chat inference with performance tracking."""
        cfg = config or self.current_config
        start = time.time()

        try:
            options = {
                "temperature": cfg.temperature,
                "top_p": cfg.top_p,
                "top_k": cfg.top_k,
                "num_predict": cfg.num_predict,
                "num_ctx": cfg.num_ctx,
                "num_batch": cfg.num_batch,
                "num_gpu": cfg.num_gpu,
                "num_thread": cfg.num_thread,
                "repeat_penalty": cfg.repeat_penalty,
            }
            if cfg.seed != -1:
                options["seed"] = cfg.seed
            if cfg.stop:
                options["stop"] = cfg.stop

            response = ollama.chat(
                model=cfg.model,
                messages=messages,
                options=options
            )

            elapsed = time.time() - start
            tokens = response.get("eval_count", 0)
            tps = tokens / elapsed if elapsed > 0 else 0

            # Update stats
            self.performance_stats["total_requests"] += 1
            self.performance_stats["total_tokens"] += tokens
            self.performance_stats["total_time"] += elapsed
            self.performance_stats["avg_tokens_per_sec"] = (
                self.performance_stats["total_tokens"] / self.performance_stats["total_time"]
                if self.performance_stats["total_time"] > 0 else 0
            )

            return {
                "success": True,
                "content": response["message"]["content"],
                "tokens": tokens,
                "time": elapsed,
                "tokens_per_sec": tps,
                "model": cfg.model
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "time": time.time() - start
            }

    def generate(self, prompt: str, config: InferenceConfig = None) -> Dict:
        """Run generation (completion) inference."""
        return self.chat([{"role": "user", "content": prompt}], config)

    def get_stats(self) -> Dict:
        return self.performance_stats.copy()

    def reset_stats(self):
        self.performance_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_time": 0.0,
            "avg_tokens_per_sec": 0.0
        }


class ModelBenchmark:
    """Benchmark models for performance comparison."""

    def __init__(self, inference_engine: InferenceEngine):
        self.engine = inference_engine

    def benchmark_model(self, model: str, test_prompts: List[str] = None,
                        config: InferenceConfig = None) -> Dict:
        """Benchmark a model with standard prompts."""
        if test_prompts is None:
            test_prompts = [
                "Explain quantum computing in simple terms.",
                "Write a Python function for binary search.",
                "What are the key principles of REST API design?",
                "Summarize the causes of World War I in 3 sentences.",
            ]

        cfg = config or InferenceConfig(model=model)
        cfg.model = model

        results = []
        total_tokens = 0
        total_time = 0

        for prompt in test_prompts:
            result = self.engine.chat(
                [{"role": "user", "content": prompt}],
                cfg
            )
            if result["success"]:
                results.append({
                    "prompt": prompt[:50] + "...",
                    "tokens": result["tokens"],
                    "time": result["time"],
                    "tps": result["tokens_per_sec"]
                })
                total_tokens += result["tokens"]
                total_time += result["time"]

        avg_tps = total_tokens / total_time if total_time > 0 else 0

        return {
            "model": model,
            "total_prompts": len(test_prompts),
            "successful": len(results),
            "total_tokens": total_tokens,
            "total_time": total_time,
            "avg_tokens_per_sec": avg_tps,
            "details": results
        }

    def compare_models(self, models: List[str], test_prompts: List[str] = None) -> List[Dict]:
        """Compare multiple models."""
        results = []
        for model in models:
            print(f"Benchmarking {model}...")
            result = self.benchmark_model(model, test_prompts)
            results.append(result)
        return sorted(results, key=lambda x: x["avg_tokens_per_sec"], reverse=True)


class ResourceMonitor:
    """Monitor system resources during inference."""

    def __init__(self):
        self.monitoring = False
        self.samples = []
        self.thread = None

    def start(self, interval: float = 1.0):
        import psutil
        self.monitoring = True
        self.samples = []

        def monitor():
            while self.monitoring:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory()
                    gpu_mem = 0
                    gpu_util = 0
                    try:
                        import GPUtil
                        gpus = GPUtil.getGPUs()
                        if gpus:
                            gpu_mem = gpus[0].memoryUsed
                            gpu_util = gpus[0].load * 100
                    except Exception:
                        pass

                    self.samples.append({
                        "timestamp": time.time(),
                        "cpu_percent": cpu,
                        "ram_percent": mem.percent,
                        "ram_used_gb": mem.used / (1024**3),
                        "gpu_mem_mb": gpu_mem,
                        "gpu_util": gpu_util
                    })
                except Exception:
                    pass
                time.sleep(interval)

        self.thread = threading.Thread(target=monitor, daemon=True)
        self.thread.start()

    def stop(self) -> Dict:
        self.monitoring = False
        if self.thread:
            self.thread.join(timeout=2)

        if not self.samples:
            return {}

        return {
            "duration": self.samples[-1]["timestamp"] - self.samples[0]["timestamp"],
            "samples": len(self.samples),
            "avg_cpu": sum(s["cpu_percent"] for s in self.samples) / len(self.samples),
            "max_cpu": max(s["cpu_percent"] for s in self.samples),
            "avg_ram": sum(s["ram_percent"] for s in self.samples) / len(self.samples),
            "max_ram": max(s["ram_percent"] for s in self.samples),
            "avg_gpu_mem": sum(s["gpu_mem_mb"] for s in self.samples) / len(self.samples),
            "max_gpu_mem": max(s["gpu_mem_mb"] for s in self.samples),
            "avg_gpu_util": sum(s["gpu_util"] for s in self.samples) / len(self.samples),
            "raw_samples": self.samples
        }


# Global instances
model_manager = ModelManager()
inference_engine = InferenceEngine()
benchmark = ModelBenchmark(inference_engine)
resource_monitor = ResourceMonitor()


# Convenience functions
def list_models():
    return model_manager.list_models()

def pull_model(name: str, progress_callback=None):
    return model_manager.pull_model(name, progress_callback)

def remove_model(name: str):
    return model_manager.remove_model(name)

def chat(messages: List[Dict], config: InferenceConfig = None):
    return inference_engine.chat(messages, config)

def generate(prompt: str, config: InferenceConfig = None):
    return inference_engine.generate(prompt, config)

def benchmark_model(model: str, prompts: List[str] = None):
    return benchmark.benchmark_model(model, prompts)

def compare_models(models: List[str], prompts: List[str] = None):
    return benchmark.compare_models(models, prompts)


if __name__ == "__main__":
    # Test
    print("=== Available Models ===")
    for m in list_models():
        print(f"  {m.name} ({m.size}) - {m.quantization} - {m.parameters}")

    print("\n=== Test Inference ===")
    result = generate("Hello, how are you?")
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Response: {result['content'][:100]}")
        print(f"Tokens: {result['tokens']}, Time: {result['time']:.2f}s, TPS: {result['tokens_per_sec']:.1f}")

    print("\n=== Stats ===")
    print(inference_engine.get_stats())