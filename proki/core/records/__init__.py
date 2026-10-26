"""Records: kinds of record the config reads and writes by name, as variables (a task, a group),
each with fields of its own and yours.

    table     a kind of record's table, as a variable: a list of its records, and one of them
    linked    a name a program reads and sets, linked to a value held elsewhere
    field     what a field of yours is made of, where a kind of record keeps them, and its jev
              or LLM questions, asked once and again only as they change
"""

from proki.core.records.linked import Linked
from proki.core.records.field import ASKS, Field, Preface
from proki.core.records.table import STAMPS, Record, Records, clock, reserved

__all__ = ["ASKS", "STAMPS", "Field", "Linked", "Preface", "Record", "Records", "clock", "reserved"]
