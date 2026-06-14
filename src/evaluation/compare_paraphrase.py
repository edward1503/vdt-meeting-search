from __future__ import annotations

from typing import Any


def summarize_metric_deltas(
    baseline: dict[str, Any],
    variants: dict[str, dict[str, Any]],
    metrics: list[str],
) -> list[dict[str, Any]]:
    baseline_by_method = {item['method']: item['metrics'] for item in baseline.get('results', [])}
    rows: list[dict[str, Any]] = []
    for condition, result in variants.items():
        for item in result.get('results', []):
            method = item['method']
            variant_metrics = item['metrics']
            base_metrics = baseline_by_method.get(method, {})
            for metric in metrics:
                base_value = float(base_metrics.get(metric, 0.0))
                variant_value = float(variant_metrics.get(metric, 0.0))
                rows.append({
                    'condition': condition,
                    'method': method,
                    'metric': metric,
                    'baseline': base_value,
                    'variant': variant_value,
                    'delta': round(variant_value - base_value, 4),
                })
    return rows
