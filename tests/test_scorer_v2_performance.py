"""Author smoke timings; independent T05b stress acceptance remains separate."""
from time import perf_counter

import pytest

from tests.test_scorer_v2 import rules
from harness.scorer_v2 import score


@pytest.mark.parametrize('size,limit', [(10000,2),(2000000,30)])
@pytest.mark.parametrize('wrong',[False,True])
def test_execution_row_limits(size,limit,wrong):
    # Distinct labels exercise hash/index lookup without a dense numeric relation.
    reference = [[str(i),i+100] for i in range(size)]
    candidate = reference.copy()
    if wrong:
        candidate[-1] = ['absent',size+99]
    start = perf_counter()
    actual = score(candidate,[reference],rules(['String','Float64']))
    elapsed = perf_counter()-start
    assert actual == ('wrong' if wrong else 'correct')
    assert elapsed <= limit, f'{size} rows: {elapsed:.3f}s > {limit}s'


@pytest.mark.parametrize('size',[1000,10000])
def test_tolerance_augmenting_paths_with_distinct_labels(size):
    ref = [[str(i),100] for i in range(size)]
    candidate = [[str(i),100.1] for i in range(size)]
    start=perf_counter()
    assert score(candidate,[ref],rules(['String','Float64'])) == 'correct'
    assert perf_counter()-start <= 2


def test_large_tie_wrong_wide_permuted_and_multiple_refs():
    ref = [[f'object-{i}',1,1]+[100*j+i for j in range(20)] for i in range(42)]
    candidate = [list(reversed(row)) for row in ref]
    candidate[-1][0] = -987654
    r=rules(['String']+['UInt64']*22, ordered=True,
            order_by=[{'column':1,'descending':True}])
    start=perf_counter()
    assert score(candidate,[ref,ref],r) == 'wrong'
    assert perf_counter()-start <= 2


def test_dense_tolerance_matching_has_linear_witness():
    reference=[[100+i/1000000] for i in range(10000)]
    candidate=[[100.001+i/1000000] for i in range(10000)]
    start=perf_counter()
    assert score(candidate,[reference],rules())=='correct'
    assert perf_counter()-start <= 2
