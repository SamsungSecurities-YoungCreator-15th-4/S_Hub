"""Dependabot이 릴리스 브랜치와 호환성 묶음 정책을 지키는지 검증한다.

통합 레포는 런타임이 셋이라 원본의 `directory: "/"` 하나만으로는 대시보드가
감시 사각지대에 남는다. 그래서 브랜치·묶음·RC 제외에 더해 **커버리지**도 함께 고정한다.
"""
from pathlib import Path

import yaml

from scripts.preflight_release import prerelease_requirement_pins

ROOT = Path(__file__).resolve().parents[1]

# 레포가 실제로 설치하는 매니페스트 전부. 하나라도 빠지면 그 런타임은 취약점 알림을 못 받는다.
# pip 는 `/` 하나로 루트 requirements.txt 와 backend/requirements.txt 를 둘 다 덮는다
# (2026-08-31 첫 실행에서 실측 — `/backend` 를 따로 두면 같은 업데이트가 두 번 열린다).
REQUIRED_COVERAGE = {
    ("pip", "/"),  # 엔진 + 대시보드 백엔드
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


def test_dependabot_groups_langstack():
    update = _pip_update_config()

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


def test_no_block_sets_target_branch():
    """target-branch 는 두지 않는다.

    main 이 이미 기본 브랜치라 불필요하고, 이 옵션을 켜면 보안 업데이트 PR 생성
    방식이 달라진다. 원본 오케스트레이션은 `develop` 을 가리키고 있었는데
    이 레포에는 그 브랜치가 없다 — 그대로 가져왔다면 조용히 실패했을 것이다.
    """
    wrong = [
        (update["package-ecosystem"], update["directory"], update["target-branch"])
        for update in _config()["updates"]
        if "target-branch" in update
    ]

    assert not wrong, f"target-branch 를 둔 블록: {wrong}"


def test_no_duplicate_ecosystem_coverage():
    """같은 매니페스트를 두 블록이 덮으면 업데이트마다 PR 이 두 개 열린다.

    2026-08-31 첫 실행에서 실제로 발생했다 — pip `/` 가 backend/requirements.txt
    까지 스캔하는데 `/backend` 블록을 따로 두어 fastapi·uvicorn·pypdf 가 중복됐다.
    """
    pip_dirs = [u["directory"] for u in _config()["updates"] if u["package-ecosystem"] == "pip"]

    assert pip_dirs == ["/"], (
        f"pip 블록은 `/` 하나여야 한다 (현재: {pip_dirs}). "
        "`/` 가 하위 requirements.txt 까지 스캔하므로 다른 pip 블록은 중복 PR 을 만든다."
    )


def test_major_updates_are_not_opened_automatically():
    """major 는 판단이 필요한 변경이라 사람이 시점을 고른다.

    첫 실행에서 openai 2→3 · typescript 5→6 · actions 4→7 이 한꺼번에 열렸다.
    """
    missing = [
        (update["package-ecosystem"], update["directory"])
        for update in _config()["updates"]
        if not any(
            rule.get("dependency-name") == "*"
            and "version-update:semver-major" in rule.get("update-types", [])
            for rule in update.get("ignore", [])
        )
    ]

    assert not missing, f"major 자동 업그레이드를 막지 않은 블록: {missing}"


def test_schedule_is_not_noisy():
    """정기 업데이트 주기는 monthly 이고 블록당 PR 상한은 작게 둔다.

    실제 취약점(security update)은 이 주기와 무관하게 즉시 열리므로
    주기를 낮춰도 보안 커버리지는 줄지 않는다.
    """
    noisy = [
        (update["package-ecosystem"], update["schedule"]["interval"], update["open-pull-requests-limit"])
        for update in _config()["updates"]
        if update["schedule"]["interval"] != "monthly" or update["open-pull-requests-limit"] > 3
    ]

    assert not noisy, f"알림이 잦은 블록: {noisy}"
