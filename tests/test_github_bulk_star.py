import importlib.util
import pathlib
import sys
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "github_bulk_star.py"
SPEC = importlib.util.spec_from_file_location("github_bulk_star", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self):
        self.starred = {"owner/already"}
        self.created = []
        self.listed = []

    def list_first_page(self, owner):
        self.listed.append(owner)
        return [
            MODULE.Repository(owner, "one"),
            MODULE.Repository(owner, "two"),
        ]

    def is_starred(self, repository):
        return repository.full_name.casefold() in self.starred

    def star(self, repository):
        self.created.append(repository.full_name)
        self.starred.add(repository.full_name.casefold())


class ParseLinkTests(unittest.TestCase):
    def test_parses_profile_repositories_page(self):
        link = MODULE.parse_link("https://github.com/mollyhan-ai?tab=repositories")
        self.assertEqual((link.kind, link.owner, link.repo), ("profile", "mollyhan-ai", None))

    def test_parses_direct_repository(self):
        link = MODULE.parse_link("https://github.com/openai/codex")
        self.assertEqual((link.kind, link.owner, link.repo), ("repository", "openai", "codex"))

    def test_rejects_issue_link(self):
        with self.assertRaises(MODULE.BulkStarError):
            MODULE.parse_link("https://github.com/openai/codex/issues/1")

    def test_rejects_plain_profile(self):
        with self.assertRaises(MODULE.BulkStarError):
            MODULE.parse_link("https://github.com/mollyhan-ai")


class ClientTests(unittest.TestCase):
    def test_retries_one_transient_transport_failure(self):
        response = mock.MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = b"[]"
        with mock.patch.object(
            MODULE.urllib.request,
            "urlopen",
            side_effect=[MODULE.urllib.error.URLError("temporary"), response],
        ) as urlopen, mock.patch.object(MODULE.time, "sleep"):
            status, body = MODULE.GitHubClient().request("GET", "/users/test/repos")
        self.assertEqual((status, body), (200, b"[]"))
        self.assertEqual(urlopen.call_count, 2)


class ResolveTests(unittest.TestCase):
    def test_mixes_link_types_and_deduplicates(self):
        client = FakeClient()
        repositories, duplicates = MODULE.resolve_repositories(
            [
                "https://github.com/alice?tab=repositories",
                "https://github.com/alice/one",
                "https://github.com/bob/solo",
            ],
            client,
        )
        self.assertEqual([repo.full_name for repo in repositories], ["alice/one", "alice/two", "bob/solo"])
        self.assertEqual(duplicates, 1)
        self.assertEqual(client.listed, ["alice"])

    def test_rejects_more_than_six_links(self):
        with self.assertRaises(MODULE.BulkStarError):
            MODULE.resolve_repositories(["https://github.com/a/r"] * 7, FakeClient())


class ApplyTests(unittest.TestCase):
    def test_skips_existing_star_and_stars_new_repository(self):
        client = FakeClient()
        result = MODULE.apply_stars(
            [MODULE.Repository("owner", "already"), MODULE.Repository("owner", "new")],
            client,
        )
        self.assertEqual(result["skipped"], ["owner/already"])
        self.assertEqual(result["starred"], ["owner/new"])
        self.assertEqual(result["failed"], [])
        self.assertEqual(client.created, ["owner/new"])


if __name__ == "__main__":
    unittest.main()
