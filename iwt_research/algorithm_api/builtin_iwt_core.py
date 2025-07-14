from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..native import get_native_capability
from ..pipeline.config import RunConfig
from ..run_experiment import run_toy_iwt
from ..secure_hash.run_hash_experiment import run_hash_experiment_sponge, write_hash_report
from ..secure_hash.toy_sponge import ToySpongeConfig
from ..stream_cipher.run_stream_experiment import run_stream_experiment, write_stream_report
from ..stream_cipher.toy_prg import ToyPRGConfig
from ..report import write_report
from .protocols import AnalyzeRequest


def _ensure_iwt_core_backend() -> None:
    capability = get_native_capability().as_dict()
    if not bool(capability.get("available", False)):
        reason = capability.get("reason", "native module unavailable")
        raise RuntimeError(f"IWT_CORE_REQUIRED: {reason}")
    symbols = capability.get("symbols", {})
    if not isinstance(symbols, dict):
        raise RuntimeError("IWT_CORE_REQUIRED: native capability symbols map is missing")
    missing = [k for k, v in symbols.items() if not bool(v)]
    if missing:
        missing_str = ", ".join(str(x) for x in missing)
        raise RuntimeError(f"IWT_CORE_REQUIRED: missing native symbols: {missing_str}")


def _projection_for_bits(input_bits: int) -> str:
    k = max(1, min(8, int(input_bits)))
    return f"lowbits:{k}"


@dataclass(slots=True)
class BuiltinIwtCoreAdapter:
    name: str = "builtin_iwt_core"
    execution_backend: str = "iwt_core"

    def analyze(self, request: AnalyzeRequest) -> Dict[str, Any]:
        _ensure_iwt_core_backend()
        crypto_type = str(request.crypto_type).strip().lower()
        if crypto_type == "block":
            run_config = RunConfig(
                cipher_preset="toy_spn",
                word_bits=int(request.input_bits),
                rounds=4,
                trace_count=64,
                seed=int(request.seed),
                projection=_projection_for_bits(int(request.input_bits)),
                threat_model_level=str(request.threat_model),
                baseline_ensemble_samples=8,
                bootstrap_iters=128,
                alpha=0.05,
                exhaustive=False,
            )
            report = run_toy_iwt(run_config)
            write_report(str(request.out_dir), report)
        elif crypto_type == "stream":
            stream_config = ToyPRGConfig(
                cipher_preset="toy_spn",
                word_bits=int(request.input_bits),
                rounds=4,
                cipher_seed=int(request.seed),
                lane_count=4,
                initial_value=0,
                mode="counter",
                output_length=max(16, int(request.output_bits)),
            )
            report = run_stream_experiment(stream_config, neighbor_count=4)
            write_stream_report(report, str(request.out_dir))
        elif crypto_type == "hash":
            input_bits = max(2, int(request.input_bits))
            # Keep exhaustive costs bounded while retaining a compression path over iwt_core-backed permutation.
            rate_bits = max(1, min(10, int(request.output_bits), input_bits - 1))
            capacity_bits = max(1, input_bits - rate_bits)
            hash_config = ToySpongeConfig(
                cipher_preset="toy_spn",
                word_bits=int(input_bits),
                rounds=4,
                cipher_seed=int(request.seed),
                lane_count=4,
                rate_bits=int(rate_bits),
                capacity_bits=int(capacity_bits),
            )
            report = run_hash_experiment_sponge(hash_config)
            write_hash_report(report, str(request.out_dir))
        else:
            raise ValueError(f"unsupported crypto type: {request.crypto_type!r}")

        report["requested_adapter"] = self.name
        report["execution_backend"] = "iwt_core"
        report["analyze_request"] = {
            "impl": str(request.impl),
            "crypto_type": str(request.crypto_type),
            "input_bits": int(request.input_bits),
            "output_bits": int(request.output_bits),
            "threat_model": str(request.threat_model),
        }
        return report


def create_adapter() -> BuiltinIwtCoreAdapter:
    return BuiltinIwtCoreAdapter()

