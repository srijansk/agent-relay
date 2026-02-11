"""Tests for StateDocument — create, advance, save/load round-trip, error paths."""

import pytest

from relay.protocol.state import StateDocument


class TestCreateInitialState:
    """StateDocument.create_initial() produces a clean starting state."""

    def test_create_initial(self):
        state = StateDocument.create_initial("drafting")
        assert state.stage == "drafting"
        assert state.iteration_counts == {}
        assert state.last_updated_by is None
        assert state.last_updated_at is None
        assert state.metadata == {}


class TestAdvanceState:
    """advance() updates stage, iteration count, role, and timestamp."""

    def test_advance(self):
        state = StateDocument.create_initial("drafting")
        state.advance("review", role="reviewer")

        assert state.stage == "review"
        assert state.iteration_counts["review"] == 1
        assert state.last_updated_by == "reviewer"
        assert state.last_updated_at is not None

    def test_advance_increments_count(self):
        state = StateDocument.create_initial("drafting")
        state.advance("review", role="reviewer")
        state.advance("review", role="reviewer")
        assert state.iteration_counts["review"] == 2


class TestSaveLoadRoundTrip:
    """save() then load() should reproduce an equivalent StateDocument."""

    def test_round_trip(self, tmp_path):
        state = StateDocument.create_initial("drafting")
        state.advance("review", role="reviewer")

        path = tmp_path / "state.yml"
        state.save(path)

        loaded = StateDocument.load(path)
        assert loaded.stage == state.stage
        assert loaded.iteration_counts == state.iteration_counts
        assert loaded.last_updated_by == state.last_updated_by
        # Timestamps may differ in sub-microsecond precision after YAML serialization,
        # so compare ISO strings.
        assert loaded.last_updated_at.isoformat() == state.last_updated_at.isoformat()


class TestLoadNonexistent:
    """Loading from a path that doesn't exist raises FileNotFoundError."""

    def test_file_not_found(self, tmp_path):
        missing = tmp_path / "nope.yml"
        with pytest.raises(FileNotFoundError):
            StateDocument.load(missing)


class TestLoadMalformedYAML:
    """Loading YAML that isn't a mapping raises ValueError."""

    def test_malformed(self, tmp_path):
        bad_file = tmp_path / "state.yml"
        bad_file.write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="Malformed state file"):
            StateDocument.load(bad_file)
