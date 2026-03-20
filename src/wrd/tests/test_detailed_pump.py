import pytest
from pyomo.environ import (
    units as pyunits,
    value,
    Reals,
)
from idaes.core import FlowsheetBlock
from idaes.core.util.model_statistics import degrees_of_freedom
from wrd.components.detailed_pump import main

@pytest.mark.skip
def test_stage_1_pump():
    m = main()
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 198529

@pytest.mark.component
def test_stage_2_pump():
    m = main(Qin=1029, Pin=131.2 * pyunits.psi, stage_num=2)
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 105000

@pytest.mark.skip
def test_stage_3_pump():
    # Fixed Efficiency
    m = main(Qin=384, Pin=(112.6 - 41.9) * pyunits.psi, stage_num=3) 
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 31296
