import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("publish_deployment.py")


class PublishDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.remote = Path(self.tmp.name) / "remote.git"
        self.repo = Path(self.tmp.name) / "source"
        self.repo.mkdir()
        self.git("init", "--bare", str(self.remote))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        for component in ("backend", "ai", "frontend", "db"):
            shutil.copytree(ROOT / "k8s" / component, self.repo / "k8s" / component)
        for path in ("BE/app.py", "AI/app.py", "fe/app.js"):
            file = self.repo / path
            file.parent.mkdir(exist_ok=True)
            file.write_text("initial\n")
        self.commit("initial")
        previous = self.sha()
        for component in ("backend", "ai", "frontend"):
            manifest = self.repo / "k8s" / component / "kustomization.yaml"
            manifest.write_text(manifest.read_text().replace("056c253625e73639604ab088ca475cfa675f61d7", previous))
        self.commit("record previous deployed image")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "main")
        self.source = self.sha()

    def git(self, *args, **kwargs):
        return subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True,
            check=True, **kwargs,
        ).stdout.strip()

    def sha(self):
        return self.git("rev-parse", "HEAD")

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)

    def advance(self, path="BE/app.py"):
        with (self.repo / path).open("a") as file:
            file.write("new version\n")
        self.commit("change " + path)
        self.git("push", "origin", "main")
        return self.sha()

    def publish(self, component="backend", sha=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), component, sha or self.source],
            cwd=self.repo, text=True, capture_output=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )

    def deployed(self, component):
        return self.git("--git-dir=" + str(self.remote), "show", f"gitops/dev:k8s/{component}/kustomization.yaml")

    def test_publishes_only_selected_component_without_changing_main_or_checkout(self):
        main_before = self.git("--git-dir=" + str(self.remote), "rev-parse", "main")
        db_before = self.git("rev-parse", "HEAD:k8s/db")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('newTag: "' + self.source + '"', self.deployed("backend"))
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "main"), main_before)
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "gitops/dev:k8s/db"), db_before)
        self.assertEqual(self.git("diff", "HEAD", "--"), "")
        self.assertEqual(self.sha(), self.source)

    def test_parallel_components_preserve_all_tags(self):
        def publish_client(component):
            client = Path(self.tmp.name) / ("client-" + component)
            self.git("clone", "--branch", "main", str(self.remote), str(client))
            return subprocess.run(
                [sys.executable, str(SCRIPT), component, self.source],
                cwd=client, text=True, capture_output=True,
            )

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(publish_client, ("backend", "frontend", "ai")))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for component in ("backend", "frontend", "ai"):
            self.assertIn('newTag: "' + self.source + '"', self.deployed(component))

    def test_does_not_deploy_old_source_after_newer_component_changes(self):
        new_source = self.advance()
        result = self.publish(sha=self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("superseded", result.stdout)
        self.assertEqual(self.git("ls-remote", "origin", "refs/heads/gitops/dev"), "")
        result = self.publish(sha=new_source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(new_source, self.deployed("backend"))

    def test_unrelated_source_changes_do_not_block_a_successful_build(self):
        self.advance("fe/app.js")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.source, self.deployed("backend"))

    def test_deployment_readme_change_does_not_suppress_the_only_successful_build(self):
        self.advance("k8s/backend/README.md")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("superseded", result.stdout)
        self.assertIn(self.source, self.deployed("backend"))

    def test_repeated_publication_is_idempotent(self):
        first = self.publish()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.git("--git-dir=" + str(self.remote), "rev-parse", "gitops/dev")
        second = self.publish()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "gitops/dev"), before)

    def test_delayed_build_does_not_replace_a_newer_equivalent_image(self):
        newer = self.advance("fe/app.js")
        result = self.publish(sha=newer)
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.git("--git-dir=" + str(self.remote), "rev-parse", "gitops/dev")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "gitops/dev"), before)

    def test_copies_reviewed_component_config_without_touching_other_components(self):
        service = self.repo / "k8s/backend/service.yaml"
        service.write_text(service.read_text() + "\n# reviewed configuration change\n")
        self.commit("reviewed backend configuration")
        self.git("push", "origin", "main")
        result = self.publish(sha=self.sha())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# reviewed configuration change", self.git(
            "--git-dir=" + str(self.remote), "show", "gitops/dev:k8s/backend/service.yaml"))

    def test_accepts_whitespace_on_a_valid_image_alias_line(self):
        manifest = self.repo / "k8s/backend/kustomization.yaml"
        manifest.write_text(manifest.read_text().replace("backend-green-image\n", "backend-green-image   \n"))
        self.commit("format alias")
        self.git("push", "origin", "main")
        result = self.publish(sha=self.sha())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_retries_a_rejected_push(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text('#!/bin/sh\nmarker="$(git rev-parse --git-dir)/rejected-once"\nif [ ! -e "$marker" ]; then touch "$marker"; exit 1; fi\n')
        hook.chmod(0o755)
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.source, self.deployed("backend"))

    def test_rejects_non_main_source_and_database_publication(self):
        self.git("switch", "-c", "unreviewed")
        with (self.repo / "BE/app.py").open("a") as file:
            file.write("unreviewed\n")
        self.commit("unreviewed")
        for component, sha in [("backend", self.sha()), ("db", self.source)]:
            result = self.publish(component, sha)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("ls-remote", "origin", "refs/heads/gitops/dev"), "")


if __name__ == "__main__":
    unittest.main()
