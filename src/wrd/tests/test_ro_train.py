import pytest
from pyomo.environ import value, units as pyunits
from wrd.components.ro_train import main


@pytest.mark.component
def test_ro_train1_8_19_21():
    expected_power = (196.25 + 22.7 + 29.3) * pyunits.kW
    expected_product_flow = (1608 + 635 + 198) * pyunits.gal / pyunits.min
    m = main()
    actual_power = pyunits.convert(m.fs.ro_train.total_pump_power, to_units=pyunits.kW)
    assert value(actual_power) == pytest.approx(value(expected_power), rel=0.15)

    actual_product_flow = pyunits.convert(
        m.fs.ro_train.product.properties[0].flow_vol_phase["Liq"],
        to_units=pyunits.gal / pyunits.min,
    )
    assert value(actual_product_flow) == pytest.approx(
        value(expected_product_flow), rel=0.15
    )


@pytest.mark.component
def test_ro_train1_3_13_21():
    expected_power = (189.6 + 22.8 + 24.9) * pyunits.kW
    expected_product_flow = (1404.7 + 617 + 279) * pyunits.gal / pyunits.min
    m = main(
        Qin=2452, Cin=0.503, Tin=295, Pin=101325, file="wrd_ro_inputs_3_13_21.yaml"
    )
    actual_power = pyunits.convert(m.fs.ro_train.total_pump_power, to_units=pyunits.kW)
    assert value(actual_power) == pytest.approx(value(expected_power), rel=0.15)

    actual_product_flow = pyunits.convert(
        m.fs.ro_train.product.properties[0].flow_vol_phase["Liq"],
        to_units=pyunits.gal / pyunits.min,
    )
    assert value(actual_product_flow) == pytest.approx(
        value(expected_product_flow), rel=0.15
    )
