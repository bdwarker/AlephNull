"""Transparent weighted scoring model for cross-module risk signals."""


def score(signals: dict[str, float], weights: dict[str, float]) -> float:
    """Return weighted score for the provided signals."""
    return sum(signals.get(k, 0.0) * weights.get(k, 0.0) for k in set(signals) | set(weights))
