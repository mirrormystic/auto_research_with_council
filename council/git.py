"""Git helpers for experiment tracking."""

import subprocess
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_experiment_history(cwd: Path) -> str:
    """Get all experiment branches with their full commit messages."""
    branches = run_git(
        ["branch", "--list", "exp/*", "--format=%(refname:short)"],
        cwd,
    )
    if not branches.strip():
        return "No experiments yet."

    lines = branches.strip().split("\n")
    parts = []
    for branch in lines:
        log = run_git(
            ["log", branch, "-1", "--format=== %s ==\n%B"],
            cwd,
        )
        parts.append(f"=== {branch} ===\n{log}")
    return "\n\n".join(parts)


def get_current_best(cwd: Path, direction: str) -> tuple[float | None, str | None]:
    """Find the best score and branch from experiment history."""
    branches = run_git(
        ["branch", "--list", "exp/*", "--format=%(refname:short)"],
        cwd,
    )
    if not branches.strip():
        return None, None

    best_score = None
    best_branch = None
    is_max = direction == "maximize"

    for branch in branches.strip().split("\n"):
        name = branch.strip()
        if not name:
            continue
        # Try to extract score from branch name: exp/406-description
        parts = name.removeprefix("exp/").split("-", 1)
        try:
            score = float(parts[0])
        except (ValueError, IndexError):
            continue

        if best_score is None:
            best_score = score
            best_branch = name
        elif is_max and score > best_score:
            best_score = score
            best_branch = name
        elif not is_max and score < best_score:
            best_score = score
            best_branch = name

    return best_score, best_branch


def create_experiment_branch(cwd: Path, name: str) -> None:
    """Create and checkout an experiment branch."""
    run_git(["checkout", "-b", f"exp/{name}"], cwd)


def commit_experiment(cwd: Path, files: list[str], message: str) -> str:
    """Stage files and commit. Returns short hash."""
    for f in files:
        run_git(["add", f], cwd)
    run_git(["commit", "-m", message], cwd)
    return run_git(["rev-parse", "--short", "HEAD"], cwd)


def checkout_main(cwd: Path) -> None:
    """Return to main branch."""
    run_git(["checkout", "main"], cwd)


def get_file_from_branch(cwd: Path, branch: str, filepath: str) -> str | None:
    """Read a file from a specific branch without checking it out."""
    result = subprocess.run(
        ["git", "show", f"{branch}:{filepath}"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout
    return None
