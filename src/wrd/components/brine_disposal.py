from pyomo.environ import (
    ConcreteModel,
    Var,
    Param,
    Constraint,
    TransformationFactory,
    assert_optimal_termination,
    value,
    units as pyunits,
)
from pyomo.network import Arc

from idaes.core import FlowsheetBlock, UnitModelCostingBlock
from idaes.core.util.initialization import propagate_state
from idaes.models.unit_models import StateJunction, Feed, Product
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.scaling import calculate_scaling_factors, set_scaling_factor

from watertap.costing import WaterTAPCosting
from watertap.property_models.NaCl_T_dep_prop_pack import NaClParameterBlock
from watertap.unit_models.pressure_changer import Pump
from watertap.core.solvers import get_solver

from watertap_contrib.reflo.unit_models.deep_well_injection import DeepWellInjection as BrineDisposal

from wrd.utilities import load_config, get_config_value, get_config_file
from srp.utils import touch_flow_and_conc
solver = get_solver()


def build_system(file="wrd_inputs_8_19_21.yaml"):

    m = ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    m.fs.properties = NaClParameterBlock()
    m.fs.costing = WaterTAPCosting()

    m.fs.feed = Feed(property_package=m.fs.properties)
    touch_flow_and_conc(m.fs.feed)

    m.fs.brine_disposal = FlowsheetBlock(dynamic=False)
    build_brine_disposal(m.fs.brine_disposal, file=file, prop_package=m.fs.properties)
        
    # Arcs to connect the unit models
    m.fs.feed_to_brine_disposal = Arc(
        source=m.fs.feed.outlet,
        destination=m.fs.brine_disposal.feed.inlet,
    )

    TransformationFactory("network.expand_arcs").apply_to(m)

    m.fs.properties.set_default_scaling(
        "flow_mass_phase_comp", 1e-1, index=("Liq", "H2O")
    )
    m.fs.properties.set_default_scaling(
        "flow_mass_phase_comp", 1e2, index=("Liq", "NaCl")
    )

    return m

def build_brine_disposal(blk, file="wrd_inputs_8_19_21.yaml", prop_package=None):

    if prop_package is None:
        m = blk.model()
        prop_package = m.fs.ro_properties

    blk.config_data = load_config(get_config_file(file))

    blk.feed = StateJunction(property_package=prop_package)
    touch_flow_and_conc(blk.feed)

    blk.unit = BrineDisposal(
        property_package=prop_package,
    )

    blk.feed_to_unit = Arc(
        source=blk.feed.outlet,
        destination=blk.unit.inlet,
    )

    TransformationFactory("network.expand_arcs").apply_to(blk)

    return blk

def initialize_system(m):

    m.fs.feed.initialize()
    propagate_state(m.fs.feed_to_brine_disposal)

    initialize_brine_disposal(m.fs.brine_disposal)

def initialize_brine_disposal(blk):

    blk.feed.initialize()
    propagate_state(blk.feed_to_unit)

    blk.unit.initialize()

def set_inlet_conditions(m, Qin=2637, Cin=0.5, Tin=302, Pin=101325):

    m.fs.feed.properties.calculate_state(
        var_args={
            ("flow_vol_phase", ("Liq")): Qin * pyunits.gallons / pyunits.minute,
            ("conc_mass_phase_comp", ("Liq", "NaCl")): Cin * pyunits.g / pyunits.L,
            ("pressure", None): Pin,
            ("temperature", None): Tin,
        },
        hold_state=True,
    )

def add_brine_disposal_costing(blk, costing_package=None):

    if costing_package is None:
        m = blk.model()
        m.fs.costing = costing_package = WaterTAPCosting()

    blk.costing = UnitModelCostingBlock(
        flowsheet_costing_block=costing_package,
        costing_method_arguments={"cost_method": "as_opex"},
    )
    costing_package.deep_well_injection.dwi_lcow.fix(0.49 * pyunits.USD_2021 / pyunits.m**3)

    return blk


def main(
    Qin=2637,
    Cin=0.5,
    Tin=302,
    Pin=101325,
    file="wrd_inputs_8_19_21.yaml",
    add_costing=True,
):

    m = build_system(file=file)
    calculate_scaling_factors(m)
    set_inlet_conditions(m, Qin=Qin, Cin=Cin, Tin=Tin, Pin=Pin)
    add_brine_disposal_costing(m.fs.brine_disposal)
    initialize_system(m)
    assert degrees_of_freedom(m) == 0
    results = solver.solve(m)
    assert_optimal_termination(results)

    return m

if __name__ == "__main__":
    m = main()
    # print(f"Degrees of freedom: {degrees_of_freedom(m)}")
    # results = solver.solve(m)
    # assert_optimal_termination(results)