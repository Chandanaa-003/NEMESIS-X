import unittest

import numpy as np

from app.config import get_settings
from app.services.identity_engine import (
    IdentityMatcher,
    appearance_similarity,
    extract_appearance_signature,
)


def _signature(index: int = 0, quality: float = 0.95) -> dict[str, object]:
    histogram = [0.0] * 32
    histogram[index] = 0.7
    histogram[(index + 1) % 32] = 0.2
    histogram[(index + 2) % 32] = 0.1
    return {
        "histogram": histogram,
        "aspect_ratio": 0.42,
        "quality": quality,
        "distinctiveness": 0.8,
    }


class IdentityMatcherTests(unittest.TestCase):
    def test_returning_person_with_new_track_id_matches_source_identity(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-1")
        first = matcher.assign(
            track_id=1,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=0,
            last_seen_timestamp=5,
            first_position={"x": 0.2, "y": 0.2},
            last_position={"x": 0.3, "y": 0.2},
        )
        returning = matcher.assign(
            track_id=8,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=20,
            last_seen_timestamp=24,
            first_position={"x": 0.7, "y": 0.7},
            last_position={"x": 0.8, "y": 0.7},
        )

        self.assertEqual(returning.profile.id, first.profile.id)
        self.assertEqual(returning.profile.identity_code, "P001")
        self.assertEqual(returning.profile.associated_track_ids, [1, 8])
        self.assertEqual(returning.profile.status, "probable")
        self.assertFalse(returning.is_new_identity)

    def test_simultaneous_similar_people_are_not_merged(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-2")
        first = matcher.assign(
            track_id=1,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=0,
            last_seen_timestamp=10,
        )
        second = matcher.assign(
            track_id=2,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=5,
            last_seen_timestamp=15,
        )

        self.assertNotEqual(first.profile.id, second.profile.id)
        self.assertEqual(second.profile.identity_code, "P002")

    def test_insufficient_quality_stays_unresolved(self) -> None:
        matcher = IdentityMatcher("live_session", "session-1")
        assignment = matcher.assign(
            track_id=3,
            class_name="person",
            signature=_signature(quality=0.1),
            first_seen_timestamp=0,
            last_seen_timestamp=0,
        )

        self.assertEqual(assignment.profile.status, "unknown")
        self.assertIsNone(assignment.profile.appearance_signature)
        self.assertIn("blurry", assignment.explanation)

    def test_close_candidate_scores_remain_unknown(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-ambiguous")
        first = matcher.assign(
            track_id=1,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=0,
            last_seen_timestamp=2,
        )
        duplicate = _signature()
        second_profile = first.profile.__class__(
            id="identity-2",
            identity_code="P002",
            entity_type="person",
            class_name="person",
            status="probable",
            first_seen_timestamp=0,
            last_seen_timestamp=2,
            appearance_count=1,
            associated_track_ids=[2],
            appearance_signature=duplicate,
            last_position=None,
            matching_confidence=0.0,
            matching_explanation="Synthetic competing candidate.",
            track_intervals={2: (0, 2)},
        )
        matcher.profiles.append(second_profile)
        matcher._tracks[2] = second_profile
        settings = get_settings()
        original_margin = settings.identity_match_margin
        settings.identity_match_margin = 0.5
        try:
            ambiguous = matcher.assign(
                track_id=3,
                class_name="person",
                signature=_signature(),
                first_seen_timestamp=20,
                last_seen_timestamp=22,
            )
        finally:
            settings.identity_match_margin = original_margin

        self.assertEqual(ambiguous.profile.status, "unknown")
        self.assertIn("too close", ambiguous.explanation)

    def test_different_object_appearance_does_not_match_by_category(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-3")
        first = matcher.assign(
            track_id=11,
            class_name="backpack",
            signature=_signature(4),
            first_seen_timestamp=0,
            last_seen_timestamp=2,
            first_position={"x": 0.2, "y": 0.2},
            last_position={"x": 0.2, "y": 0.2},
        )
        second = matcher.assign(
            track_id=12,
            class_name="backpack",
            signature=_signature(20),
            first_seen_timestamp=20,
            last_seen_timestamp=22,
            first_position={"x": 0.2, "y": 0.2},
            last_position={"x": 0.2, "y": 0.2},
        )

        self.assertLess(appearance_similarity(_signature(4), _signature(20)), 0.5)
        self.assertNotEqual(first.profile.id, second.profile.id)
        self.assertEqual(first.profile.identity_code, "O001")
        self.assertEqual(second.profile.identity_code, "O002")

    def test_object_match_needs_distinctive_appearance_and_nearby_context(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-object-match")
        first = matcher.assign(
            track_id=11,
            class_name="backpack",
            signature=_signature(4),
            first_seen_timestamp=0,
            last_seen_timestamp=2,
            first_position={"x": 0.2, "y": 0.2},
            last_position={"x": 0.2, "y": 0.2},
        )
        returning = matcher.assign(
            track_id=12,
            class_name="backpack",
            signature=_signature(4),
            first_seen_timestamp=10,
            last_seen_timestamp=12,
            first_position={"x": 0.21, "y": 0.2},
            last_position={"x": 0.21, "y": 0.2},
        )

        self.assertEqual(returning.profile.id, first.profile.id)
        self.assertEqual(returning.profile.identity_code, "O001")
        self.assertEqual(returning.profile.status, "probable")

    def test_object_can_match_after_a_supported_relocation(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-object-moved")
        settings = get_settings()
        original_threshold = settings.identity_object_similarity_threshold
        settings.identity_object_similarity_threshold = 0.92
        try:
            first = matcher.assign(
                track_id=21,
                class_name="suitcase",
                signature=_signature(9),
                first_seen_timestamp=0,
                last_seen_timestamp=2,
                first_position={"x": 0.1, "y": 0.2},
                last_position={"x": 0.1, "y": 0.2},
            )
            relocated = matcher.assign(
                track_id=22,
                class_name="suitcase",
                signature=_signature(9),
                first_seen_timestamp=20,
                last_seen_timestamp=23,
                first_position={"x": 0.6, "y": 0.2},
                last_position={"x": 0.6, "y": 0.2},
            )
        finally:
            settings.identity_object_similarity_threshold = original_threshold

        self.assertEqual(relocated.profile.id, first.profile.id)
        self.assertEqual(relocated.profile.associated_track_ids, [21, 22])
        self.assertIn("Possible appearance match", relocated.explanation)

    def test_simultaneous_similar_objects_are_not_merged(self) -> None:
        matcher = IdentityMatcher("analysis", "analysis-object-overlap")
        first = matcher.assign(
            track_id=31,
            class_name="backpack",
            signature=_signature(3),
            first_seen_timestamp=0,
            last_seen_timestamp=10,
            first_position={"x": 0.3, "y": 0.4},
            last_position={"x": 0.3, "y": 0.4},
        )
        second = matcher.assign(
            track_id=32,
            class_name="backpack",
            signature=_signature(3),
            first_seen_timestamp=5,
            last_seen_timestamp=15,
            first_position={"x": 0.3, "y": 0.4},
            last_position={"x": 0.3, "y": 0.4},
        )

        self.assertNotEqual(first.profile.id, second.profile.id)
        self.assertEqual(second.profile.identity_code, "O002")

    def test_blurry_crop_and_separate_sources_do_not_create_false_matches(self) -> None:
        frame = np.zeros((120, 120, 3), dtype=np.uint8)
        signature = extract_appearance_signature(
            frame,
            {"x1": 10, "y1": 10, "x2": 90, "y2": 110},
            "person",
        )
        self.assertIsNotNone(signature)
        self.assertEqual(signature["quality"], 0.0)

        first_source = IdentityMatcher("analysis", "source-a").assign(
            track_id=1,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=0,
            last_seen_timestamp=1,
        )
        second_source = IdentityMatcher("analysis", "source-b").assign(
            track_id=1,
            class_name="person",
            signature=_signature(),
            first_seen_timestamp=0,
            last_seen_timestamp=1,
        )

        self.assertEqual(first_source.profile.identity_code, "P001")
        self.assertEqual(second_source.profile.identity_code, "P001")
        self.assertNotEqual(first_source.profile.id, second_source.profile.id)


if __name__ == "__main__":
    unittest.main()