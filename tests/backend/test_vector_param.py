"""vector_param must be a drop-in replacement for binding a Python list.

The string form exists purely for speed (the duckdb client's list transform
costs ~170 ms for a 3072-dim vector); these tests pin the contract that the
SQL-side ::FLOAT[N] cast parses it back to the exact same float32 vector a
list bind would produce.
"""

import math
import random

import duckdb
import pytest

from backend.services.embeddings import DIMENSIONS, vector_param

# Values chosen to stress repr round-tripping: subnormal-ish magnitudes,
# many significant digits, exact binary fractions, negatives, and zero.
PRECISION_STRESS = [0.0, -0.0, 1e-30, -1e30, 0.1, 1 / 3, -2.5, 123456.789e-12]


@pytest.fixture
def conn():
    with duckdb.connect() as c:
        yield c


def test_matches_list_binding_exactly(conn):
    vec = PRECISION_STRESS + [random.Random(42).uniform(-1, 1) for _ in range(64)]
    n = len(vec)
    via_list = conn.execute(f"SELECT ?::FLOAT[{n}]", [vec]).fetchone()[0]
    via_str = conn.execute(f"SELECT ?::FLOAT[{n}]", [vector_param(vec)]).fetchone()[0]
    assert via_str == via_list


def test_same_cosine_similarity_as_list_binding(conn):
    rng = random.Random(7)
    stored = [rng.uniform(-1, 1) for _ in range(DIMENSIONS)]
    query = [rng.uniform(-1, 1) for _ in range(DIMENSIONS)]
    conn.execute(f"CREATE TABLE t (v FLOAT[{DIMENSIONS}])")
    conn.execute(f"INSERT INTO t VALUES (?::FLOAT[{DIMENSIONS}])", [vector_param(stored)])

    sql = f"SELECT array_cosine_similarity(v, ?::FLOAT[{DIMENSIONS}]) FROM t"
    sim_list = conn.execute(sql, [query]).fetchone()[0]
    sim_str = conn.execute(sql, [vector_param(query)]).fetchone()[0]
    assert sim_str == sim_list
    assert math.isfinite(sim_str)


def test_wrong_dimension_still_rejected(conn):
    """The cast must keep enforcing the declared array size."""
    with pytest.raises(duckdb.ConversionException):
        conn.execute("SELECT ?::FLOAT[4]", [vector_param([1.0, 2.0])]).fetchone()
