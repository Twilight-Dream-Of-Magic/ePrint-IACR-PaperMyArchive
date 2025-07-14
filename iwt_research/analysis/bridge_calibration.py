from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

from .baseline_models import (
    RandomARXLikeBaseline,
    RandomFunctionBaseline,
    RandomPermutationBaseline,
    RandomSubstitutionPermutationNetworkBaseline,
    RandomSubstitutionPermutationNetworkVectorBaseline,
)
from ..metrics.observation_metrics import (
    compute_observation_self_intersection_rate,
    compute_one_step_predictor_success_from_traces,
)
from ..projections.projections import parse_projection
from ..ciphers.runner_factory import build_toy_cipher_from_config
from ..run_helpers import build_trace_state_indices, run_trace_from_state_index


@dataclass(frozen=True, slots=True)
class BridgeCalibrationConfig:
    instance_samples: int = 50
    baseline_instance_samples: int = 200
    attack_success_quantile: float = 0.99
    target_fdr: float = 0.05
    split_seed: int = 0


def _quantile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    q = min(1.0, max(0.0, float(q)))
    idx = int(round(q * (len(sorted_values) - 1)))
    return float(sorted_values[idx])


def _empirical_fdr_tpr(*, B: List[bool], D: List[bool]) -> Dict[str, Any]:
    tp = sum(1 for b, d in zip(B, D) if d and b)
    fp = sum(1 for b, d in zip(B, D) if d and (not b))
    tn = sum(1 for b, d in zip(B, D) if (not d) and (not b))
    fn = sum(1 for b, d in zip(B, D) if (not d) and b)
    fdr_hat = float(fp) / float(max(1, tp + fp))
    tpr_hat = float(tp) / float(max(1, tp + fn))
    return {
        "TP": int(tp),
        "FP": int(fp),
        "TN": int(tn),
        "FN": int(fn),
        "FDR_hat": float(fdr_hat),
        "TPR_hat": float(tpr_hat),
        "trigger_count": int(tp + fp),
    }


def _choose_theta_by_split_sample(
    *,
    scores_train: List[float],
    B_train: List[bool],
    scores_test: List[float],
    B_test: List[bool],
    target_fdr: float,
) -> Dict[str, Any]:
    # Candidate thresholds: unique score values (sorted descending => stricter triggers).
    candidates = sorted({float(s) for s in scores_train if s == s}, reverse=True)
    if not candidates:
        candidates = [float("inf")]

    best = None
    for theta in candidates:
        D_train = [float(s) >= float(theta) for s in scores_train]
        m_train = _empirical_fdr_tpr(B=B_train, D=D_train)
        ok = bool(float(m_train["FDR_hat"]) <= float(target_fdr))
        # Objective: satisfy FDR constraint, then maximize TPR, then maximize trigger_count (more data), then minimize theta.
        key = (
            1 if ok else 0,
            float(m_train["TPR_hat"]),
            float(m_train["trigger_count"]),
            -float(theta),
        )
        if best is None or key > best["key"]:
            best = {"theta": float(theta), "train": m_train, "key": key, "constraint_met": ok}

    assert best is not None
    theta = float(best["theta"])
    D_test = [float(s) >= float(theta) for s in scores_test]
    m_test = _empirical_fdr_tpr(B=B_test, D=D_test)
    return {
        "theta": float(theta),
        "selection": {
            "target_fdr": float(target_fdr),
            "met_constraint_on_train": bool(best["constraint_met"]),
        },
        "train": best["train"],
        "test": m_test,
    }


def _make_cipher_runner(*, preset: str, word_bits: int, lane_count: int, rounds: int, seed: int, rot_mode: str, rot_dir: str, cross_domain_q: int | None, cross_every_rounds: int) -> Any:
    return build_toy_cipher_from_config(
        {
            "cipher_preset": str(preset),
            "word_bits": int(word_bits),
            "lane_count": int(lane_count),
            "rounds": int(rounds),
            "seed": int(seed),
            "rotation_mode": str(rot_mode),
            "rotation_direction": str(rot_dir),
            "cross_domain_modulus": cross_domain_q,
            "cross_every_rounds": int(cross_every_rounds),
        }
    )


def _make_baseline_runner(
    *,
    baseline_family: str,
    runner: Any,
    rounds: int,
    lane_count: int,
    seed: int,
    word_bits: int,
    rot_mode: str,
    rot_dir: str,
    cross_domain_q: int | None,
    cross_every_rounds: int,
) -> Any:
    # Align step count for permutation/function baselines.
    _, evs0 = runner.run(0)
    steps = int(len(evs0))
    name = str(baseline_family)
    if name == "random_arx_like":
        return RandomARXLikeBaseline(
            domain=runner.domain,
            rounds=int(rounds),
            seed=int(seed),
            word_bits=int(word_bits),
            rot_mode=str(rot_mode),
            rot_dir=str(rot_dir),
            cross_domain_q=cross_domain_q,
            cross_every_rounds=int(cross_every_rounds),
        )
    if name == "random_substitution_permutation_network":
        return RandomSubstitutionPermutationNetworkBaseline(domain=runner.domain, rounds=int(rounds), seed=int(seed))
    if name == "random_substitution_permutation_network_vector":
        return RandomSubstitutionPermutationNetworkVectorBaseline(domain=runner.domain, rounds=int(rounds), lane_count=int(lane_count), seed=int(seed))
    if name == "random_permutation":
        return RandomPermutationBaseline(domain=runner.domain, steps=int(steps), seed=int(seed))
    return RandomFunctionBaseline(domain=runner.domain, steps=int(steps), seed=int(seed))


def run_bridge_calibration(
    *,
    preset: str,
    word_bits: int,
    lane_count: int,
    rounds: int,
    seed: int,
    ntraces: int,
    projection_spec: str,
    rot_mode: str = "bits",
    rot_dir: str = "l",
    cross_domain_q: int | None = None,
    cross_every_rounds: int = 4,
    baseline_family: str = "random_permutation",
    calibration_config: BridgeCalibrationConfig | None = None,
) -> Dict[str, Any]:
    """
    Paper 10.3.E1 (minimal runnable): split-sample calibration for screening quality.

    - Risk score D: based on observation-side self-intersection (mean over traces)
    - Attack success event B: one-step predictor success exceeds a baseline quantile
    """
    calibration_config = calibration_config or BridgeCalibrationConfig()
    inst_n = max(4, int(calibration_config.instance_samples))
    base_n = max(20, int(calibration_config.baseline_instance_samples))

    # Fixed start distribution over state indices (pre-registered within this run).
    trace_sampling_config = {
        "cipher_preset": str(preset),
        "lane_count": int(lane_count),
        "trace_count": int(ntraces),
        "seed": int(seed),
        "exhaustive": False,
        "max_empirical_trace_count": max(int(ntraces), 64),
    }
    _, proj_fn = parse_projection(str(projection_spec), word_bits=int(word_bits))

    # Instance family: vary cipher seed (toy "key") deterministically.
    instance_seeds = [int(seed) + i for i in range(inst_n)]

    # Build a representative runner to align baselines.
    runner0 = _make_cipher_runner(
        preset=preset,
        word_bits=int(word_bits),
        lane_count=int(lane_count),
        rounds=int(rounds),
        seed=int(instance_seeds[0]),
        rot_mode=str(rot_mode),
        rot_dir=str(rot_dir),
        cross_domain_q=cross_domain_q,
        cross_every_rounds=int(cross_every_rounds),
    )

    trace_state_indices = build_trace_state_indices(
        runner=runner0,
        run_config=trace_sampling_config,
        seed_xor=0xA91C_E001,
    )

    # Baseline distribution for attack success threshold.
    succ_base: List[float] = []
    for ensemble_index in range(base_n):
        base = _make_baseline_runner(
            baseline_family=str(baseline_family),
            runner=runner0,
            rounds=int(rounds),
            lane_count=int(lane_count),
            seed=(int(seed) ^ 0x51A1_7E01) + ensemble_index,
            word_bits=int(word_bits),
            rot_mode=str(rot_mode),
            rot_dir=str(rot_dir),
            cross_domain_q=cross_domain_q,
            cross_every_rounds=int(cross_every_rounds),
        )
        traces: List[List[int]] = []
        for s in trace_state_indices[: min(len(trace_state_indices), 64)]:
            states, _ = run_trace_from_state_index(
                runner=base,
                state_index=int(s),
                run_config=trace_sampling_config,
            )
            traces.append([int(proj_fn(st)) for st in states])
        succ_base.append(float(compute_one_step_predictor_success_from_traces(traces=traces)))

    succ_base_sorted = sorted(float(x) for x in succ_base)
    succ_threshold = _quantile(succ_base_sorted, float(calibration_config.attack_success_quantile))

    # Evaluate each tested instance: risk score + attack success.
    scores: List[float] = []
    succs: List[float] = []
    Bs: List[bool] = []
    for k_seed in instance_seeds:
        runner = _make_cipher_runner(
            preset=preset,
            word_bits=int(word_bits),
            lane_count=int(lane_count),
            rounds=int(rounds),
            seed=int(k_seed),
            rot_mode=str(rot_mode),
            rot_dir=str(rot_dir),
            cross_domain_q=cross_domain_q,
            cross_every_rounds=int(cross_every_rounds),
        )
        traces = []
        for s in trace_state_indices[: min(len(trace_state_indices), 64)]:
            states, _ = run_trace_from_state_index(
                runner=runner,
                state_index=int(s),
                run_config=trace_sampling_config,
            )
            traces.append([int(proj_fn(st)) for st in states])
        # D-score: mean self-intersection across traces.
        per_trace_si = [float(compute_observation_self_intersection_rate(observations=t)) for t in traces]
        score = float(sum(per_trace_si) / float(len(per_trace_si))) if per_trace_si else 0.0
        succ = float(compute_one_step_predictor_success_from_traces(traces=traces))
        B = bool(float(succ) >= float(succ_threshold))
        scores.append(float(score))
        succs.append(float(succ))
        Bs.append(bool(B))

    # split-sample (instances)
    rng = random.Random(int(calibration_config.split_seed))
    idx = list(range(inst_n))
    rng.shuffle(idx)
    mid = max(1, len(idx) // 2)
    train_idx = idx[:mid]
    test_idx = idx[mid:]
    scores_train = [scores[i] for i in train_idx]
    B_train = [Bs[i] for i in train_idx]
    scores_test = [scores[i] for i in test_idx]
    B_test = [Bs[i] for i in test_idx]

    selection = _choose_theta_by_split_sample(
        scores_train=scores_train,
        B_train=B_train,
        scores_test=scores_test,
        B_test=B_test,
        target_fdr=float(calibration_config.target_fdr),
    )

    return {
        "protocol": {
            "paper": "10.3.E1 minimal split-sample calibration",
            "risk_score": "mean_observation_self_intersection_rate",
            "attack_class": "one_step_predictor",
            "attack_success_event_B": {
                "definition": f"Succ_pred >= quantile_{calibration_config.attack_success_quantile} of baseline Succ_pred",
                "baseline_family": str(baseline_family),
                "succ_threshold": float(succ_threshold),
            },
        },
        "config": {
            "cipher_preset": str(preset),
            "word_bits": int(word_bits),
            "lane_count": int(lane_count),
            "rounds": int(rounds),
            "seed": int(seed),
            "trace_count": int(ntraces),
            "projection_spec": str(projection_spec),
            "rotation_mode": str(rot_mode),
            "rotation_direction": str(rot_dir),
            "cross_domain_modulus": cross_domain_q,
            "cross_every_rounds": int(cross_every_rounds),
            "instance_samples": int(inst_n),
            "baseline_instance_samples": int(base_n),
            "split_seed": int(calibration_config.split_seed),
            "target_fdr": float(calibration_config.target_fdr),
        },
        "baseline_succ_pred": {
            "samples_head": list(float(x) for x in succ_base_sorted[: min(32, len(succ_base_sorted))]),
            "quantile": float(calibration_config.attack_success_quantile),
            "threshold": float(succ_threshold),
        },
        "instances": {
            "instance_seeds_head": list(int(x) for x in instance_seeds[: min(16, len(instance_seeds))]),
            "scores_head": list(float(x) for x in scores[: min(16, len(scores))]),
            "succ_pred_head": list(float(x) for x in succs[: min(16, len(succs))]),
            "B_head": list(bool(x) for x in Bs[: min(16, len(Bs))]),
        },
        "split_sample": selection,
    }


def write_bridge_calibration(out_dir: str, data: Dict[str, Any]) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "bridge_calibration.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
