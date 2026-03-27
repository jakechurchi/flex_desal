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

@pytest.mark.skip
def test_stage_2_pump():
    m = main(Qin=1029, Pin=131.2 * pyunits.psi, stage_num=2)
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 17498

@pytest.mark.skip
def test_stage_3_pump():
    # Fixed Efficiency
    m = main(Qin=384, Pin=(112.6 - 41.9) * pyunits.psi, stage_num=3) 
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 31296

@pytest.mark.component
def test_uf_pump():
    m = main(
        Qin=3300, # This number is just a guess, actual flowrate calculated from model
        Pin= -12 * pyunits.psi,
        stage_num=1,
        uf=True,
        uf_pump_speed=0.91,
    )
    assert pytest.approx(value(pyunits.convert(m.fs.pump.feed.properties[0].flow_vol_phase["Liq"],to_units=pyunits.gallon/pyunits.minute)), rel=1e-3) == 3824.7
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 160777

# Seems to solve even with a pretty poor guess
@pytest.mark.component
def test_uf_pump_bad_guess():
    with pytest.raises(
        RuntimeError,
        match=r"Check initial flowrate guess is reasonable as solver did not find an optimal solution with head and speed fixed.*",
    ):
        m = main(
            Qin=2000, # This number is just a guess, actual flowrate calculated from model
            Pin= -12 * pyunits.psi,
            stage_num=1,
            uf=True,
            uf_pump_speed=0.91,
        )