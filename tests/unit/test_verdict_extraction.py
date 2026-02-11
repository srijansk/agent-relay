"""Tests for extract_verdict() — markdown verdict parsing."""

import pytest

from relay.protocol.state import extract_verdict

FIELD = "Verdict"
APPROVE = "APPROVE"
REJECT = "REQUEST_CHANGES"


class TestVerdictApprove:
    """Standard '## Verdict: APPROVE' returns 'approve'."""

    def test_h2_approve(self):
        content = "Some preamble.\n\n## Verdict: APPROVE\n\nDetails here."
        assert extract_verdict(content, FIELD, APPROVE, REJECT) == "approve"


class TestVerdictReject:
    """'## Verdict: REQUEST_CHANGES' returns 'reject'."""

    def test_h2_reject(self):
        content = "Review notes.\n\n## Verdict: REQUEST_CHANGES\n\nPlease fix."
        assert extract_verdict(content, FIELD, APPROVE, REJECT) == "reject"


class TestVerdictLowercaseH1:
    """'# Verdict: approve' (lowercase, h1) returns 'approve'."""

    def test_h1_lowercase(self):
        content = "# Verdict: approve\n"
        assert extract_verdict(content, FIELD, APPROVE, REJECT) == "approve"


class TestVerdictSpaceBeforeColon:
    """'## Verdict : APPROVE' (space before colon) returns 'approve'."""

    def test_space_before_colon(self):
        content = "## Verdict : APPROVE\n"
        assert extract_verdict(content, FIELD, APPROVE, REJECT) == "approve"


class TestVerdictMissing:
    """Content without a verdict heading returns None."""

    def test_missing(self):
        content = "Just a regular document.\n\nNo verdict here."
        assert extract_verdict(content, FIELD, APPROVE, REJECT) is None


class TestVerdictUnmatchedValue:
    """Verdict heading present but value doesn't match either option returns None."""

    def test_unmatched(self):
        content = "## Verdict: MAYBE\n"
        assert extract_verdict(content, FIELD, APPROVE, REJECT) is None
