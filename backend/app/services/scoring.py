"""
Algeo Verify — Scoring Engine
===============================
Computes a confidence score (0.0–1.0) for a detected address based on
which entity fields were successfully extracted, and generates risk flags
for any missing fields.

Usage:
    from app.services.detection import detectEntities
    from app.services.scoring import ScoringEngine

    entities = detectEntities(normalized)
    score, flags = ScoringEngine().computeScore(entities)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Tuple

from app.services.detection import DetectedEntities


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RiskFlag:
    """A single risk indicator for a missing or weak address field."""
    label: str
    severity: Literal["low", "medium", "high"]
    description: str


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------

class ScoringEngine:
    """Weighted scoring engine for address verification.

    Each entity field contributes a fixed weight to the overall confidence
    score.  Fields that are ``None`` (not detected) reduce the score and
    produce a corresponding :class:`RiskFlag`.

    Weights (fixed):
        - wilaya:     0.35
        - commune:    0.30
        - postalCode: 0.15
        - street:     0.20
    """

    def __init__(self) -> None:
        self.weight_wilaya: float = 0.35
        self.weight_commune: float = 0.30
        self.weight_postale: float = 0.15
        self.weight_street: float = 0.20

    # ---- internal mapping ------------------------------------------------

    def _field_specs(self) -> List[Tuple[str, str, float, Literal["low", "medium", "high"]]]:
        """Return (field_attr, human_label, weight, severity) for each field."""
        return [
            ("wilaya",     "Wilaya",      self.weight_wilaya,  "high"),
            ("commune",    "Commune",     self.weight_commune, "medium"),
            ("postalCode", "Postal Code", self.weight_postale, "low"),
            ("street",     "Street",      self.weight_street,  "low"),
        ]

    # ---- public API ------------------------------------------------------

    def computeScore(
        self, detected_entities: DetectedEntities
    ) -> Tuple[float, List[RiskFlag]]:
        """Compute confidence score and risk flags for *detected_entities*.

        Args:
            detected_entities: The output of
                :func:`app.services.detection.detectEntities`.

        Returns:
            A tuple ``(confidence_score, risk_flags)`` where
            *confidence_score* is a float between 0.0 and 1.0, and
            *risk_flags* is a (possibly empty) list of :class:`RiskFlag`
            objects describing missing fields.
        """
        score: float = 0.0
        risk_flags: List[RiskFlag] = []

        for attr, label, weight, severity in self._field_specs():
            value = getattr(detected_entities, attr, None)
            if value is not None:
                score += weight
            else:
                risk_flags.append(
                    RiskFlag(
                        label=f"Missing {label}",
                        severity=severity,
                        description=f"{label} could not be detected in the address.",
                    )
                )

        # Clamp to [0.0, 1.0] for safety (weights already sum to 1.0)
        score = round(min(max(score, 0.0), 1.0), 2)

        return score, risk_flags


# ---------------------------------------------------------------------------
# Quick self-test — run from backend/ folder:
#   .venv\Scripts\python.exe -m app.services.scoring
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    from app.services.normalization import normalize
    from app.services.detection import detectEntities

    engine = ScoringEngine()

    test_cases = [
        "123 rue Didouche Mourad, Constantine 25000",
        "Oran, Bir El Djir 31003",
        "16000",
        "  ",
    ]

    print("=" * 72)
    print("  Algeo Verify — Scoring Engine — Self-Test")
    print("=" * 72)

    for raw in test_cases:
        norm = normalize(raw)
        entities = detectEntities(norm)
        score, flags = engine.computeScore(entities)

        print(f"\n  RAW   : {raw!r}")
        print(f"  SCORE : {score}")
        if flags:
            for f in flags:
                print(f"  FLAG  : [{f.severity.upper()}] {f.label} — {f.description}")
        else:
            print("  FLAGS : (none)")

    print("\n" + "=" * 72)
    print("  \u2713 All test cases processed successfully")
    print("=" * 72)
