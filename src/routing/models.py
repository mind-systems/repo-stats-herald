from dataclasses import dataclass
from enum import Enum


class BranchRole(Enum):
    RELEASE = "release"
    STAGING = "staging"
    DEV = "dev"


@dataclass(frozen=True, slots=True)
class DeliveryPlan:
    branch_role: BranchRole
    is_release: bool
    is_prerelease: bool
