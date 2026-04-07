import pytest
from pyomo.environ import (
    units as pyunits,
    value,
)
from wrd.components.detailed_pump import main


# THESE TESTS SHOULD BE MOVED TO THE TEST DAY AND REPLACED WITH 1E-3 APPROX TESTS ONCE MERGED WITH STANDARDIZE TESTING
@pytest.mark.unit
def test_stage_1_pump():
    m = main()
    expected_power = 196.25  # kW
    assert value(
        pyunits.convert(m.fs.pump.unit.work_mechanical[0], to_units=pyunits.kW)
    ) == pytest.approx(expected_power, rel=0.15)


@pytest.mark.unit
def test_stage_2_pump():
    m = main(
        Qin=1047, Pin=143.5 * pyunits.psi, stage_num=2, file="wrd_inputs_3_13_21.yaml"
    )
    expected_power = 22.7  # kW
    assert value(
        pyunits.convert(m.fs.pump.unit.work_mechanical[0], to_units=pyunits.kW)
    ) == pytest.approx(expected_power, rel=0.5) #change to 0.15
    # assert value(m.fs.pump.unit.design_speed_fraction) == pytest.approx(0.5, rel=1e-3)


@pytest.mark.unit
def test_stage_3_pump():
    # Fixed Efficiency
    m = main(Qin=384, Pin=(112.6 - 41.9) * pyunits.psi, stage_num=3)
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 31296


@pytest.mark.unit
def test_uf_pump():
    # Currently a head and speed input, but should change to flow and head (or flow and speed)
    m = main(
        Qin=3300,  # This number is just a guess, actual flowrate calculated from model
        Pin=-12 * pyunits.psi,
        stage_num=1,
        uf=True,
    )
    
    assert pytest.approx(m.fs.pump.unit.work_mechanical[0].value, rel=1e-3) == 118535
    assert pytest.approx(m.fs.pump.unit.design_speed_fraction.value, rel=1e-3) == 0.804

# This is outdated, but would be nice to catch if the user provides flowrate / head outside the bounds of validity for their surrogate
# @pytest.mark.unit
# def test_uf_pump_bad_guess():
#     with pytest.raises(
#         RuntimeError,
#         match=r"Check initial flowrate guess is reasonable as solver did not find an optimal solution with head and speed fixed.*",
#     ):
#         m = main(
#             Qin=200,  # This number is just a guess, actual flowrate calculated from model
#             Pin=-12 * pyunits.psi,
#             stage_num=1,
#             uf=True,
#         )
