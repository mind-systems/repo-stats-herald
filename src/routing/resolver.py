from src.core.config import Settings
from src.routing.models import BranchRole, DeliveryPlan

RELEASE_BRANCHES = ("master", "main")
STAGING_BRANCH = "staging"


def role_for_branch(branch: str) -> BranchRole:
    if branch in RELEASE_BRANCHES:
        return BranchRole.RELEASE
    if branch == STAGING_BRANCH:
        return BranchRole.STAGING
    return BranchRole.DEV


class DeliveryPlanResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self, org_id: int, repo: str, branch: str) -> DeliveryPlan:
        branch_role = role_for_branch(branch)
        return DeliveryPlan(
            branch_role=branch_role,
            is_release=branch_role is BranchRole.RELEASE,
            is_prerelease=branch_role is BranchRole.STAGING,
        )
