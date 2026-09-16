from __future__ import annotations

from pddl.conditions import Atom


class DisjunctiveExistentialRule:
    def __init__(self, head: list[Atom], body: list[Atom]):
        self.head = head
        self.body = body

    def _is_datalog_rule(self):
        return False
