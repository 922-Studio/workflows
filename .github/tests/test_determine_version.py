"""Tests for determine_version.py: get_version_bump_from_commits() and CLI routing."""

import sys
import os
import pytest

# Add scripts directory to path so we can import determine_version
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from determine_version import get_version_bump_from_commits


class TestGetVersionBumpFromCommits:
    """Tests for get_version_bump_from_commits() function."""

    # --- PATCH cases ---

    def test_fix_prefix_returns_patch(self):
        """Single fix commit returns PATCH."""
        assert get_version_bump_from_commits("fix: correct typo") == "PATCH"

    def test_chore_prefix_returns_patch(self):
        """Single chore commit returns PATCH."""
        assert get_version_bump_from_commits("chore: update deps") == "PATCH"

    def test_ci_prefix_returns_patch(self):
        """Single ci commit returns PATCH."""
        assert get_version_bump_from_commits("ci: update runner") == "PATCH"

    def test_bare_message_returns_patch(self):
        """Non-conventional commit message returns PATCH."""
        assert get_version_bump_from_commits("Merge pull request #123") == "PATCH"

    def test_empty_string_returns_patch(self):
        """Empty string returns PATCH."""
        assert get_version_bump_from_commits("") == "PATCH"

    # --- MINOR cases ---

    def test_feat_prefix_returns_minor(self):
        """Single feat commit returns MINOR."""
        assert get_version_bump_from_commits("feat: add login") == "MINOR"

    def test_feat_with_scope_returns_minor(self):
        """feat(scope): commit returns MINOR."""
        assert get_version_bump_from_commits("feat(auth): add OAuth") == "MINOR"

    # --- MAJOR cases ---

    def test_feat_bang_returns_major(self):
        """feat!: commit returns MAJOR."""
        assert get_version_bump_from_commits("feat!: redesign API") == "MAJOR"

    def test_fix_bang_with_scope_returns_major(self):
        """fix(scope)!: commit returns MAJOR."""
        assert get_version_bump_from_commits("fix(ui)!: breaking layout change") == "MAJOR"

    def test_breaking_change_footer_returns_major(self):
        """BREAKING CHANGE: in commit body returns MAJOR."""
        commits = "fix: typo\n\nBREAKING CHANGE: removed endpoint"
        assert get_version_bump_from_commits(commits) == "MAJOR"

    # --- Multi-commit highest-wins cases ---

    def test_two_commits_fix_then_feat_returns_minor(self):
        """Two commits: fix then feat returns MINOR (highest wins)."""
        commits = "fix: a\n\nfeat: b"
        assert get_version_bump_from_commits(commits) == "MINOR"

    def test_two_commits_feat_then_fix_returns_minor(self):
        """Two commits: feat then fix returns MINOR (highest wins)."""
        commits = "feat: a\n\nfix: b"
        assert get_version_bump_from_commits(commits) == "MINOR"

    def test_two_commits_fix_then_breaking_returns_major(self):
        """Two commits: fix then feat! returns MAJOR (highest wins)."""
        commits = "fix: a\n\nfeat!: b"
        assert get_version_bump_from_commits(commits) == "MAJOR"

    # --- Blank line handling ---

    def test_blank_lines_between_commits_are_skipped(self):
        """Blank lines in multi-commit output are ignored safely."""
        commits = "feat: a\n\n\nfix: b\n\n"
        assert get_version_bump_from_commits(commits) == "MINOR"

    # --- Additional edge cases ---

    def test_any_type_with_bang_returns_major(self):
        """Any commit type with ! returns MAJOR."""
        assert get_version_bump_from_commits("chore!: remove old tooling") == "MAJOR"

    def test_feat_bang_with_scope_returns_major(self):
        """feat(scope)!: returns MAJOR."""
        assert get_version_bump_from_commits("feat(api)!: breaking API redesign") == "MAJOR"

    def test_fix_prefix_with_scope_returns_patch(self):
        """fix(scope): returns PATCH."""
        assert get_version_bump_from_commits("fix(db): resolve connection leak") == "PATCH"


class TestCliRouting:
    """Tests for CLI routing: --use-ai flag presence/absence."""

    def test_main_without_use_ai_does_not_require_gemini_key(self):
        """Running without --use-ai must not raise error about GEMINI_API_KEY."""
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "determine_version.py")
        result = subprocess.run(
            [sys.executable, script, "--commits", "fix: typo", "--version-file", "/dev/null"],
            capture_output=True,
            text=True,
            env={**os.environ, "GEMINI_API_KEY": ""},
        )
        # Should NOT contain the "GEMINI_API_KEY environment variable not set" error
        assert "GEMINI_API_KEY environment variable not set" not in result.stderr

    def test_main_with_use_ai_and_no_key_exits_with_error(self):
        """Running with --use-ai and no GEMINI_API_KEY must exit with error."""
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "determine_version.py")
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        result = subprocess.run(
            [sys.executable, script, "--commits", "fix: typo", "--version-file", "/dev/null", "--use-ai"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0
        assert "GEMINI_API_KEY" in result.stderr

    def test_google_generativeai_not_required_for_import(self):
        """Importing get_version_bump_from_commits must not require google-generativeai."""
        # This test passes if the import at the top of this file succeeded.
        # The import is already done; if it raised ImportError, we'd never reach here.
        from determine_version import get_version_bump_from_commits as fn
        assert callable(fn)
