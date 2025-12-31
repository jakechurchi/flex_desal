import pytest
from pyomo.environ import value, units as pyunits
from wrd.components.UF_system import main


@pytest.mark.component
def test_uf_system_8_19_21():
    # Does this test actually pass any data specific to the date?
    m = main(num_trains=3,split_fraction=[.4,.4,.2],Qin=10416, Cin=0.5)
    power = pyunits.convert(m.fs.total_uf_pump_power, to_units=pyunits.kW)
    # expected_power = 455 * pyunits.kW # From data
    expected_power = 180 * pyunits.kW # Modeled value
    assert pytest.approx(value(power), rel=0.15) == value(expected_power)  # kWh/m3


@pytest.mark.component
def test_uf_system_3_13_21():
    # Does this test actually pass any data specific to the date?
    m = main(num_trains=3,split_fraction=[.4,.4,.2],Qin=9764, Cin=0.5)
    power = pyunits.convert(m.fs.total_uf_pump_power, to_units=pyunits.kW)
    # expected_power = 432 * pyunits.kW # From data
    expected_power = 148 * pyunits.kW # Modeled value
    assert pytest.approx(value(power), rel=0.15) == value(expected_power)  # kWh/m3


@pytest.mark.component
def test_uf_system_with_costing():
    m = main(add_costing=True)
    # Idk where the SEC values is coming from
    assert pytest.approx(value(m.fs.costing.SEC), rel=1e-3) == 0.129291  # kWh/m3

@pytest.mark.component
def test_uf_system_even_split():
    m = main()
    power = pyunits.convert(m.fs.total_uf_pump_power, to_units=pyunits.kW)
    expected_power = 76 * pyunits.kW  # Modeled Value
    assert pytest.approx(value(power), rel=0.15) == value(expected_power)  # kWh/m3
