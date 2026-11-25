from dataclasses import dataclass
from functools import lru_cache
import re

from app.services.detector import COMMON_COCO_CATEGORIES


_TRACK_CODE_RE = re.compile(r"(?<![A-Z0-9])([POT])\s*0*(\d{1,8})(?!\d)", re.IGNORECASE)
_NUMERIC_TRACK_RE = re.compile(r"\btrack\s*#?\s*0*(\d{1,8})\b", re.IGNORECASE)
_TIMESTAMP_RE = re.compile(
    r"(?<!\d)(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)(?:\.(\d{1,3}))?(?!\d)"
)
_STOP_WORDS = {
    "a", "an", "and", "at", "by", "did", "during", "find", "for", "from",
    "in", "involving", "of", "on", "show", "the", "to", "when", "where",
    "with", "all", "available", "evidence", "event", "events", "between", "left", "object",
    "objects", "person", "people", "track", "tracks", "video", "videos",
}
_CLASS_ALIASES = {
    "person": "person",
    "people": "person",
    "persons": "person",
    "pedestrian": "person",
    "pedestrians": "person",
    "man": "person",
    "woman": "person",
    "backpack": "backpack",
    "backpacks": "backpack",
    "handbag": "handbag",
    "handbags": "handbag",
    "suitcase": "suitcase",
    "suitcases": "suitcase",
    "luggage": "suitcase",
    "car": "car",
    "cars": "car",
    "vehicle": "vehicle",
    "vehicles": "vehicle",
    "truck": "truck",
    "trucks": "truck",
    "bus": "bus",
    "buses": "bus",
    "train": "train",
    "trains": "train",
    "motorcycle": "motorcycle",
    "motorcycles": "motorcycle",
    "bicycle": "bicycle",
    "bicycles": "bicycle",
    "bike": "bicycle",
    "bikes": "bicycle",
    "dog": "dog",
    "dogs": "dog",
    "cat": "cat",
    "cats": "cat",
    "bottle": "bottle",
    "bottles": "bottle",
    "chair": "chair",
    "chairs": "chair",
    "laptop": "laptop",
    "laptops": "laptop",
    "phone": "cell phone",
    "cellphone": "cell phone",
    "cellphones": "cell phone",
    "book": "book",
    "books": "book",
}
_VEHICLE_CLASSES = frozenset(
    {"bicycle", "bus", "car", "motorcycle", "train", "truck"}
)
_EVENT_INTENTS = (
    (re.compile(r"\b(approach(?:ed|es|ing)?|interact(?:ion(?:s)?|ed|ing)?|pickup(?:s)?|pick\s+up|placement(?:s)?|placed)\b"), ("object_interactions",)),
    (re.compile(r"\b(unattended|stationary|left\s+behind|removal|removed)\b"), ("possible_unattended_objects", "object_interactions")),
    (re.compile(r"\b(zone|restricted|enter(?:ed|ing|y)?|exit(?:ed|ing)?|loiter(?:ing)?)\b"), ("people_movement", "other_activities")),
    (re.compile(r"\b(unusual|anomal(?:y|ies|ous)|direction\s+change|rapid\s+movement)\b"), ("people_movement", "other_activities")),
)


@dataclass(frozen=True)
class ParsedSearchQuery:
    track_id: int | None
    track_role: str | None
    class_terms: tuple[str, ...]
    event_categories: tuple[str, ...]
    event_terms: tuple[str, ...]
    text_terms: tuple[str, ...]
    start_seconds: float | None
    end_seconds: float | None
    evidence_requested: bool
    supported: bool


def _time_to_seconds(match: re.Match[str]) -> float:
    first, second, third, fraction = match.groups()
    if first is None:
        hours = 0
        minutes = int(second)
        seconds = int(third)
    else:
        hours = int(first)
        minutes = int(second)
        seconds = int(third)
    decimal = float(f"0.{fraction}") if fraction else 0.0
    return hours * 3600 + minutes * 60 + seconds + decimal


@lru_cache(maxsize=256)
def parse_search_query(query: str) -> ParsedSearchQuery:
    """Parse common search phrases deterministically; never consults an external model."""
    normalized = " ".join(query.lower().split())
    track_match = _TRACK_CODE_RE.search(query)
    if track_match:
        prefix, raw_id = track_match.groups()
        track_id = int(raw_id)
        track_role = {"p": "person", "o": "object"}.get(prefix.lower())
    else:
        numeric_match = _NUMERIC_TRACK_RE.search(normalized)
        track_id = int(numeric_match.group(1)) if numeric_match else None
        track_role = None

    time_matches = list(_TIMESTAMP_RE.finditer(query))
    parsed_times = [_time_to_seconds(match) for match in time_matches[:2]]

    class_terms: list[str] = []
    matched_class_words: set[str] = set()
    for alias in sorted(_CLASS_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            canonical = _CLASS_ALIASES[alias]
            if canonical not in class_terms:
                class_terms.append(canonical)
            matched_class_words.add(alias)
    for class_name in sorted(COMMON_COCO_CATEGORIES, key=len, reverse=True):
        variants = (class_name, f"{class_name}s")
        for variant in variants:
            if re.search(rf"\b{re.escape(variant)}\b", normalized):
                if class_name not in class_terms:
                    class_terms.append(class_name)
                matched_class_words.update(re.findall(r"[a-z]+", variant))

    event_categories: list[str] = []
    event_terms: list[str] = []
    matched_event_words: set[str] = set()
    for pattern, categories in _EVENT_INTENTS:
        matches = pattern.findall(normalized)
        if matches:
            for category in categories:
                if category not in event_categories:
                    event_categories.append(category)
            matched_event_words.update(
                re.findall(r"[a-z]+", pattern.pattern.replace(r"\b", "").replace(r"\s+", " "))
            )
            for match in pattern.finditer(normalized):
                matched_event_words.update(match.group(0).split())
                term = match.group(0).replace(" ", "_")
                if term not in event_terms:
                    event_terms.append(term)

    text_without_times = _TIMESTAMP_RE.sub(" ", normalized)
    text_without_ids = _TRACK_CODE_RE.sub(" ", text_without_times)
    text_without_ids = _NUMERIC_TRACK_RE.sub(" ", text_without_ids)
    tokens = re.findall(r"[a-z]+", text_without_ids)
    text_terms = tuple(
        dict.fromkeys(
            token for token in tokens
            if token not in _STOP_WORDS
            and token not in matched_class_words
            and token not in matched_event_words
            and token not in {"possible", "potential", "sequence", "movement", "zone"}
        )
    )
    evidence_requested = bool(re.search(r"\bevidence\b", normalized))
    supported = bool(
        track_id is not None
        or class_terms
        or event_categories
        or parsed_times
        or evidence_requested
    )
    return ParsedSearchQuery(
        track_id=track_id,
        track_role=track_role,
        class_terms=tuple(class_terms),
        event_categories=tuple(event_categories),
        event_terms=tuple(event_terms),
        text_terms=text_terms,
        start_seconds=parsed_times[0] if parsed_times else None,
        end_seconds=parsed_times[1] if len(parsed_times) > 1 else None,
        evidence_requested=evidence_requested,
        supported=supported,
    )


def class_matches(class_name: str, class_term: str) -> bool:
    normalized = " ".join(class_name.lower().split())
    if class_term == "vehicle":
        return normalized in _VEHICLE_CLASSES
    return normalized == class_term


def format_track_code(track_id: int) -> str:
    return f"T{track_id:03d}"
