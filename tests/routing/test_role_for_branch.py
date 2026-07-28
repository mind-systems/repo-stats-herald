from src.core.config import Settings
from src.routing.models import BranchRole
from src.routing.resolver import DeliveryPlanResolver, role_for_branch


def test_release_branches_classify_as_release():
    assert role_for_branch("main") is BranchRole.RELEASE
    assert role_for_branch("master") is BranchRole.RELEASE


def test_staging_branch_classifies_as_staging():
    assert role_for_branch("staging") is BranchRole.STAGING


def test_other_branches_classify_as_dev():
    assert role_for_branch("feature/x") is BranchRole.DEV


def test_similar_but_not_exact_names_fall_to_dev():
    assert role_for_branch("main-backup") is BranchRole.DEV
    assert role_for_branch("staging2") is BranchRole.DEV


def test_resolve_derives_flags_from_role():
    resolver = DeliveryPlanResolver(Settings(github_webhook_secret="x"))

    release_plan = resolver.resolve(org_id=1, repo="repo", branch="main")
    assert release_plan.branch_role is BranchRole.RELEASE
    assert release_plan.is_release is True
    assert release_plan.is_prerelease is False

    staging_plan = resolver.resolve(org_id=1, repo="repo", branch="staging")
    assert staging_plan.branch_role is BranchRole.STAGING
    assert staging_plan.is_release is False
    assert staging_plan.is_prerelease is True

    dev_plan = resolver.resolve(org_id=1, repo="repo", branch="feature/x")
    assert dev_plan.branch_role is BranchRole.DEV
    assert dev_plan.is_release is False
    assert dev_plan.is_prerelease is False
