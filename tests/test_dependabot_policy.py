"""Dependabot이 릴리스 브랜치와 호환성 묶음 정책을 지키는지 검증한다.

통합 레포는 런타임이 셋이라 원본의 `directory: "/"` 하나만으로는 대시보드가
감시 사각지대에 남는다. 그래서 브랜치·묶음·RC 제외에 더해 **커버리지**도 함께 고정한다.
"""
from pathlib import Path

import yaml

from scripts.preflight_release import prerelease_requirement_pins

ROOT = Path(__file__).resolve().parents[1]

# S_Hub 는 develop 없이 main 단일 브랜치로 운영한다. 없는 브랜치를 target 으로 두면
# Dependabot 이 PR 을 열지 못하고 조용히 실패한다.
RELEASE_BRANCH = "main"

# 레포가 실제로 설치하는 매니페스트 전부. 하나라도 빠지면 그 런타임은 취약점 알림을 못 받는다.
REQUIRED_COVERAGE = {
    ("pip", "/"),  # 엔진 — requirements.txt
    ("pip", "/backend"),  # 대시보드 백엔드 — backend/requirements.txt
    ("npm", "/frontend"),  # 대시보드 프론트 — frontend/package.json
    ("github-actions", "/"),  # CI 액션 핀
}


def _config() -> dict:
    return yaml.safe_load(
        (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )


def _pip_update_config() -> dict:
    config = _config()
    return next(
        update
        for update in config["updates"]
        if update["package-ecosystem"] == "pip" and update["directory"] == "/"
    )


def test_dependabot_targets_release_branch_and_groups_langstack():
    update = _pip_update_config()

    assert update["target-branch"] == RELEASE_BRANCH
    assert set(update["groups"]["langstack"]["patterns"]) == {
        "langchain*",
        "langgraph*",
        "langsmith",
    }


def test_dependabot_excludes_known_release_candidate():
    update = _pip_update_config()
    ignored_versions = {
        version
        for rule in update["ignore"]
        if rule["dependency-name"] == "langgraph"
        for version in rule["versions"]
    }

    assert "1.0.10rc1" in ignored_versions


def test_repository_requirements_do_not_pin_prereleases():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert prerelease_requirement_pins(requirements) == []


def test_every_runtime_manifest_is_watched():
    """감시 커버리지 — 매니페스트가 하나라도 빠지면 그 런타임은 알림을 못 받는다."""
    covered = {
        (update["package-ecosystem"], update["directory"])
        for update in _config()["updates"]
    }

    assert REQUIRED_COVERAGE <= covered, (
        f"Dependabot 감시에서 빠진 매니페스트: {sorted(REQUIRED_COVERAGE - covered)}"
    )


def test_every_update_targets_the_release_branch():
    """존재하지 않는 브랜치를 target 으로 두면 PR 이 열리지 않고 조용히 실패한다."""
    wrong = [
        (update["package-ecosystem"], update["directory"], update.get("target-branch"))
        for update in _config()["updates"]
        if update.get("target-branch") != RELEASE_BRANCH
    ]

    assert not wrong, f"{RELEASE_BRANCH} 이외를 target 으로 둔 블록: {wrong}"
