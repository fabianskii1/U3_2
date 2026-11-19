"""Publish a tested component's manifests to gitops/dev using ordinary Git pushes."""

import argparse
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from update_image_tag import image_tag, update_tag


BRANCH = "gitops/dev"
COMPONENTS = {
    "backend": ("backend-green-image", ["BE", "AI/workflow", ".github/workflows/build.yaml"]),
    "frontend": ("frontend-image", ["fe", ".github/workflows/build-fe.yaml"]),
    "ai": ("ai-blue-image", ["AI", ".github/workflows/build-ai.yaml"]),
}


def git(*args, check=True, **kwargs):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=check, **kwargs)


def ancestor(older, newer):
    result = git("merge-base", "--is-ancestor", older, newer, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip())
    return result.returncode == 0


def publish(component, sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected a full source commit SHA")
    alias, sources = COMPONENTS[component]
    directory = f"k8s/{component}"
    manifest = f"{directory}/kustomization.yaml"
    last_error = ""
    for attempt in range(5):
        git("fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
        if not ancestor(sha, "origin/main"):
            raise ValueError("Source commit is not on main")
        diff = git("diff", "--quiet", sha, "origin/main", "--", *sources, f":(glob){directory}/*.yaml", check=False)
        if diff.returncode == 1:
            print(f"Skip {component}: source superseded by newer main changes")
            return
        if diff.returncode:
            raise RuntimeError(diff.stderr.strip())
        remote = git("ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}").stdout.strip()
        if remote:
            git("fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
        parent = git("rev-parse", f"origin/{BRANCH}" if remote else "origin/main").stdout.strip()
        current = git("show", f"{parent}:{manifest}").stdout
        previous = image_tag(current, alias)
        if re.fullmatch(r"[0-9a-f]{40}", previous) and previous != sha and ancestor(sha, previous):
            print(f"Skip {component}: a newer image is already published")
            return
        source = git("show", f"{sha}:{manifest}").stdout
        updated = update_tag(source, alias, sha)
        # A private index builds a commit without altering the runner's checkout or index.
        with tempfile.TemporaryDirectory(prefix="gitops-index-") as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            git("read-tree", parent, env=env)
            files = git("ls-files", "-z", "--", directory, env=env).stdout
            if files:
                git("update-index", "--force-remove", "-z", "--stdin", input=files, env=env)
            git("read-tree", f"--prefix={directory}/", f"{sha}:{directory}", env=env)
            blob = git("hash-object", "-w", "--stdin", input=updated).stdout.strip()
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{manifest}", env=env)
            tree = git("write-tree", env=env).stdout.strip()
        if tree == git("rev-parse", f"{parent}^{{tree}}").stdout.strip():
            if remote:
                print(f"No change: {component} already uses {sha}")
                return
            commit = parent
        else:
            commit = git(
                "-c", "user.name=github-actions[bot]",
                "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "commit-tree", tree, "-p", parent,
                input=f"deploy({component}): {sha}\n",
            ).stdout.strip()
        pushed = git("push", "origin", f"{commit}:refs/heads/{BRANCH}", check=False)
        if pushed.returncode == 0:
            print(f"Published {component}:{sha} to {BRANCH} ({commit[:7]})")
            return
        last_error = pushed.stderr.strip()
        time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(f"Deployment push failed after five attempts: {last_error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=COMPONENTS)
    parser.add_argument("sha")
    args = parser.parse_args()
    publish(args.component, args.sha)
