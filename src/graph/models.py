import enum
from dataclasses import dataclass


class EdgeKind(enum.StrEnum):
    CONTRACT = "CONTRACT"
    AUTH = "AUTH"
    DEPENDENCY = "DEPENDENCY"


@dataclass(frozen=True)
class Edge:
    from_repo: str
    to_repo: str
    kind: EdgeKind
    source: str
