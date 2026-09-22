"""
Module 3: Versioned Weights & Configuration Store, AHP Elicitation Engine, and Sensitivity Analyzer.
Every constant, weight, threshold, and anchor lives here with timestamped versioning.
"""

from __future__ import annotations
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field


class SubIndexWeights(BaseModel):
    w_M: float = Field(default=0.28, description="Moisture state weight")
    w_R: float = Field(default=0.14, description="Rate of change weight")
    w_T: float = Field(default=0.12, description="Thermal anomaly weight")
    w_A: float = Field(default=0.18, description="Accumulated mould risk weight")
    w_F: float = Field(default=0.18, description="Forecast risk weight")
    w_V: float = Field(default=0.10, description="Vulnerability rubric weight")

    def as_dict(self) -> Dict[str, float]:
        return {
            "s_M": self.w_M,
            "s_R": self.w_R,
            "s_T": self.w_T,
            "s_A": self.w_A,
            "s_F": self.w_F,
            "s_V": self.w_V,
        }


class AnchorsConfig(BaseModel):
    m_safe: float = 14.0
    m_crit: float = 17.0
    dm_dt_scale: float = 0.5
    t_diff_min: float = 2.0
    t_diff_max: float = 8.0
    mra_scale: float = 6.0
    r72_scale: float = 50.0
    rhf_offset: float = 70.0
    rhf_span: float = 25.0
    mra_crit: float = 6.0


class AlertLadderConfig(BaseModel):
    watch_threshold: float = 25.0
    priority_threshold: float = 50.0
    critical_threshold: float = 75.0
    hysteresis_points: float = 10.0
    dwell_watch_hours: float = 3.0
    dwell_priority_hours: float = 2.0
    dwell_critical_minutes: float = 30.0
    deescalate_dwell_hours: float = 6.0


class ConfigVersion(BaseModel):
    version_id: int
    timestamp: datetime
    author: str
    rationale: str
    weights: SubIndexWeights
    anchors: AnchorsConfig
    alert_ladder: AlertLadderConfig


# Random Inconsistency Index (RI) for n = 1 to 10 (Saaty 1980)
RI_TABLE = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


class WeightsStore:
    def __init__(self):
        self.versions: List[ConfigVersion] = []
        # Seed initial default version 1
        v1 = ConfigVersion(
            version_id=1,
            timestamp=datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc),
            author="System Baseline",
            rationale="Initial default engineering weights based on rough rice storage physics",
            weights=SubIndexWeights(),
            anchors=AnchorsConfig(),
            alert_ladder=AlertLadderConfig(),
        )
        self.versions.append(v1)

    @property
    def current(self) -> ConfigVersion:
        return self.versions[-1]

    def create_version(
        self,
        weights: SubIndexWeights,
        anchors: Optional[AnchorsConfig] = None,
        alert_ladder: Optional[AlertLadderConfig] = None,
        author: str = "Supervisor",
        rationale: str = "AHP re-elicitation",
    ) -> ConfigVersion:
        new_v = ConfigVersion(
            version_id=len(self.versions) + 1,
            timestamp=datetime.now(timezone.utc),
            author=author,
            rationale=rationale,
            weights=weights,
            anchors=anchors or self.current.anchors,
            alert_ladder=alert_ladder or self.current.alert_ladder,
        )
        self.versions.append(new_v)
        return new_v

    @staticmethod
    def solve_ahp_matrix(pairwise_matrix: List[List[float]]) -> Tuple[List[float], float, float, bool]:
        """
        Solves 6x6 pairwise comparison matrix for weights using principal eigenvector method.
        Returns: (normalized_weights, lambda_max, consistency_ratio, is_consistent)
        Consistent if CR < 0.10.
        """
        A = np.array(pairwise_matrix, dtype=float)
        n = A.shape[0]
        if n != 6:
            raise ValueError("AHP matrix must be 6x6 for the 6 sub-indices")

        # Compute eigenvalues and eigenvectors
        eigenvalues, eigenvectors = np.linalg.eig(A)
        
        # Principal eigenvalue is the one with the maximum real part
        max_idx = np.argmax(np.real(eigenvalues))
        lambda_max = float(np.real(eigenvalues[max_idx]))
        
        # Principal eigenvector (normalized to sum to 1)
        w = np.real(eigenvectors[:, max_idx])
        w = np.abs(w)  # Perron-Frobenius theorem ensures positive eigenvector
        w = w / np.sum(w)
        
        # Consistency Index (CI) and Consistency Ratio (CR)
        ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
        ri = RI_TABLE.get(n, 1.24)
        cr = ci / ri if ri > 0 else 0.0
        
        is_consistent = cr < 0.10
        weights_list = [round(float(x), 4) for x in w]
        return weights_list, round(lambda_max, 4), round(cr, 4), is_consistent

    def compute_sensitivity_analysis(
        self,
        active_stack_sub_indices: Dict[str, Dict[str, float]],
        perturbation_fraction: float = 0.30,  # ±30%
    ) -> Dict[str, Any]:
        """
        Perturbs each weight by ±30% one at a time, renormalizes remainder,
        and reports the change in top-6 stack rankings.
        """
        base_weights = self.current.weights.as_dict()
        sub_index_keys = ["s_M", "s_R", "s_T", "s_A", "s_F", "s_V"]

        def compute_ranking(w_dict: Dict[str, float]) -> List[str]:
            scores = []
            for stk_id, s_vec in active_stack_sub_indices.items():
                epi = 100.0 * sum(w_dict[k] * s_vec.get(k, 0.0) for k in sub_index_keys)
                scores.append((stk_id, epi))
            scores.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in scores[:6]]

        baseline_top6 = compute_ranking(base_weights)
        sensitivity_results = {}

        for key in sub_index_keys:
            orig_w = base_weights[key]
            for direction, factor in [("plus_30", 1.0 + perturbation_fraction), ("minus_30", 1.0 - perturbation_fraction)]:
                perturbed = base_weights.copy()
                new_w = orig_w * factor
                diff = new_w - orig_w
                other_sum = sum(v for k, v in base_weights.items() if k != key)
                
                # Renormalize other weights
                perturbed[key] = new_w
                if other_sum > 0:
                    for k in perturbed:
                        if k != key:
                            perturbed[k] = max(0.0, perturbed[k] - diff * (perturbed[k] / other_sum))
                total_w = sum(perturbed.values())
                for k in perturbed:
                    perturbed[k] /= total_w
                    
                rank_res = compute_ranking(perturbed)
                rank_changed = (rank_res != baseline_top6)
                sensitivity_results[f"{key}_{direction}"] = {
                    "sub_index": key,
                    "direction": direction,
                    "perturbed_weight": round(perturbed[key], 4),
                    "top6_ranking": rank_res,
                    "ranking_shifted": rank_changed,
                }

        return {
            "baseline_top6": baseline_top6,
            "perturbation_percent": round(perturbation_fraction * 100.0, 1),
            "analyses": sensitivity_results,
        }
