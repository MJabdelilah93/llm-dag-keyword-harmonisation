"""Mandatory comprehension check shown before diabetes re-annotation can
begin (diagnostic Step 6). All six examples are synthetic and generic --
NONE come from the CE or diabetes benchmark, and responses here are
training only and are never written to any benchmark file.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ComprehensionExample:
    string_a: str
    string_b: str
    correct_label: str
    explanation: str


# Six synthetic, non-benchmark examples covering the six required concepts.
COMPREHENSION_EXAMPLES: list[ComprehensionExample] = [
    ComprehensionExample(
        "automobile", "car", "match",
        "MATCH: these are ordinary synonyms for the same everyday concept.",
    ),
    ComprehensionExample(
        "colour", "color", "match",
        "MATCH: this is a spelling/format variant of the same concept.",
    ),
    ComprehensionExample(
        "vehicle", "car", "non-match",
        "NON-MATCH: 'vehicle' is BROADER than 'car' (a vehicle can be a car, truck, bus, etc.). "
        "Broader/narrower pairs are always NON-MATCH, even though the terms are clearly related.",
    ),
    ComprehensionExample(
        "teacher", "school", "non-match",
        "NON-MATCH: these are related (a teacher works at a school) but they denote DIFFERENT concepts, "
        "not the same one. Related-but-distinct pairs are NON-MATCH.",
    ),
    ComprehensionExample(
        "ADA", "accessibility law", "uncertain",
        "UNCERTAIN: 'ADA' is an ambiguous acronym (it could mean several different things in different "
        "contexts, e.g. a disability-rights law or a professional dental association). When an acronym is "
        "ambiguous and cannot be resolved from the strings alone, the correct answer is UNCERTAIN.",
    ),
    ComprehensionExample(
        "xz19-q##", "unspecified process variant", "uncertain",
        "UNCERTAIN: one side is a malformed/opaque string and the other is vague and context-dependent -- "
        "equivalence cannot be reliably determined, so the correct answer is UNCERTAIN.",
    ),
]

ALLOWED_LABELS = ("match", "non-match", "uncertain")

REFRESHED_INSTRUCTIONS_LINES = [
    "# Refreshed instructions before diabetes re-annotation",
    "",
    "MATCH: same underlying concept; safe to harmonise.",
    "",
    "NON-MATCH: different concepts, INCLUDING broader/narrower and related-but-distinct terms.",
    "",
    "UNCERTAIN: equivalence cannot be determined reliably from the strings and the permitted "
    "up-to-three-title context.",
    "",
    "IMPORTANT REMINDER:",
    "Do not choose MATCH merely because both terms concern the same disease, topic, or research area.",
    "This is particularly important in this biomedical domain, where many distinct concepts "
    "(different conditions, mechanisms, measurements, or treatments) can superficially seem related "
    "just because they belong to the same broader disease area.",
]


class ComprehensionGateState:
    """Pure state machine for the gate -- no Tkinter here, so it is
    unit-testable headlessly. current_index advances only on a correct
    answer; an incorrect answer must be retried on the SAME example."""

    def __init__(self):
        self.current_index = 0
        self.last_result_correct: bool | None = None
        self.last_explanation: str = ""

    @property
    def total(self) -> int:
        return len(COMPREHENSION_EXAMPLES)

    @property
    def is_complete(self) -> bool:
        return self.current_index >= self.total

    def current_example(self) -> ComprehensionExample:
        return COMPREHENSION_EXAMPLES[self.current_index]

    def answer(self, label: str) -> bool:
        if label not in ALLOWED_LABELS:
            raise ValueError(f"label must be one of {ALLOWED_LABELS}, got {label!r}")
        example = self.current_example()
        correct = label == example.correct_label
        self.last_result_correct = correct
        self.last_explanation = example.explanation
        if correct:
            self.current_index += 1
        return correct
