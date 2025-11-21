import pathlib
from pyomo.environ import (
    ConcreteModel,
    value,
    TransformationFactory,
    Param,
    Var,
    Constraint,
    Set,
    Expression,
    Objective,
    NonNegativeReals,
    Block,
    RangeSet,
    check_optimal_termination,
    assert_optimal_termination,
    units as pyunits,
)
from pyomo.network import Arc, SequentialDecomposition
from pyomo.util.check_units import assert_units_consistent
from pyomo.util.calc_var_value import calculate_variable_from_constraint as cvc

from idaes.core import FlowsheetBlock, UnitModelCostingBlock
from idaes.core.util.initialization import propagate_state
from idaes.core.util.scaling import (
    constraint_scaling_transform,
    calculate_scaling_factors,
    set_scaling_factor,
)
from idaes.models.unit_models import Product, Feed, StateJunction, Separator
from idaes.core.util.model_statistics import *
from idaes.core.surrogate.surrogate_block import SurrogateBlock

from watertap.core.solvers import get_solver
from watertap.core import Database
from watertap.unit_models.zero_order import ChemicalAdditionZO
from watertap.core.wt_database import Database
# from watertap.core.zero_order_properties import WaterParameterBlock
from watertap.property_models.NaCl_T_dep_prop_pack import NaClParameterBlock
from watertap.core.util.model_diagnostics.infeasible import *
from watertap.costing.zero_order_costing import ZeroOrderCosting
from watertap.core.util.initialization import *

def build_system(**kwargs):
    m = ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    m.fs.ro_properties = NaClParameterBlock()
    m.fs.uv_aop_system = FlowsheetBlock(dynamic=False)
    build_UV(m.fs.uv_aop_system, prop_package=m.fs.ro_properties, **kwargs)
    return m


def build_UV(blk, prop_package):

    blk.feed = StateJunction(property_package=prop_package)
    blk.product = StateJunction(property_package=prop_package)
    blk.unit = StateJunction(property_package=prop_package)

    blk.unit.power_consumption = Var(
        initialize=0,
        domain=NonNegativeReals,
        units=pyunits.kW,
        doc="Power consumption of UV_aop",
    )
   
    blk.feed_to_UV = Arc(source = blk.feed.inlet,destination= blk.unit.inlet)
    blk.UV_to_product = Arc(source=blk.unit.outlet, destination = blk.product.inlet)
    TransformationFactory("network.expand_arcs").apply_to(blk)


def set_UV_op_conditions(blk):
    # surrogate
    power_surrogate = PysmoSurrogate.load_from_file("UV_surr_rbf_linear.json")
    blk.power_surrogate = SurrogateBlock()
    # define inputs and outputs as lists of Pyomo Var objects
    inputs = blk.feed.properties[0].flow_vol
    outputs = blk.unit.power_consumption
    blk.power_surrogate.build_model(
        power_surrogate, input_vars=[inputs], output_vars=[outputs]
    )

    blk.unit.power_use = Constraint(
        Expression=blk.unit.power_consumption
        == blk.power_surrogate.evaluate(blk.feed.properties[0].vol_flow)
    )

def set_inlet_conditions(blk, Qin=.5*0.154, Cin=2*0.542):
    """
    Set the operation conditions for the UV. 
    """
    Qin = (Qin) * pyunits.m**3 / pyunits.s  # Feed flow rate in m3/s
    Cin = Cin * pyunits.g / pyunits.L  # Feed concentration in g/L
    rho = 1000 * pyunits.kg / pyunits.m**3  # Approximate density of water
    feed_mass_flow_water = Qin * rho
    feed_mass_flow_salt = Cin * Qin

    blk.feed_in.properties[0].flow_mass_phase_comp["Liq", "H2O"].fix(
        feed_mass_flow_water
    )
    blk.feed_in.properties[0].flow_mass_phase_comp["Liq", "NaCl"].fix(
        feed_mass_flow_salt
    )
    blk.feed_in.properties[0].temperature.fix(298.15 * pyunits.K)  # 25 C
    blk.feed_in.properties[0].pressure.fix(P_in * pyunits.bar)
    blk.feed_in.properties[0].flow_vol  # Touching


def initialize_UV(blk):
    blk.feed.initialize()
    propagate_state(blk.feed_to_UV)
    blk.unit.initialize()
    propagate_state(blk.UV_to_product)
    blk.product.intitialize()
  
def add_UV_scaling(blk):
    set_scaling_factor(blk.unit.power_consumption,1e-3)

def cost_UV(blk):
    # Not including capital costs?
    lb = blk.unit.power_consumption.lb
    # set lower bound to 0 to avoid negative defined flow warning when lb is not >= 0
    blk.unit.power_consumption.setlb(0)
    blk.costing_package.cost_flow(blk.unit.power_consumption, "electricity")
    # set lower bound back to its original value that was assigned to lb
    blk.unit_model.work_mechanical.setlb(lb)

def report_UV(blk):
    title = "UV Report"
    side = int(((3 * w) - len(title)) / 2) - 1
    header = "=" * side + f" {title} " + "=" * side
    print(f"\n{header}\n")
    print(f'{"Parameter":<{w}s}{"Value":<{w}s}{"Units":<{w}s}')
    print(f"{'-' * (3 * w)}")

    total_flow = blk.feed.properties[0].flow_vol
    power = blk.unit.power_consumption
    print(
        f'{f"Total Flow Rate (MGD)":<{w}s}{value(pyunits.convert(total_flow, to_units=pyunits.Mgallons /pyunits.day)):<{w}.3f}{"MGD"}'
    )
    print(f'{f"Total Flow Rate (m3/s)":<{w}s}{value(total_flow):<{w}.3e}{"m3/s"}')
    print(
        f'{f"Total Flow Rate (gpm)":<{w}s}{value(pyunits.convert(total_flow, to_units=pyunits.gallons / pyunits.minute)):<{w}.3f}{"gpm"}'
    )
    print(
        f'{f"Work Mech. (kW)":<{w}s}{value(pyunits.convert(power, to_units=pyunits.kW)):<{w}.3f}{"kW"}'
    )

if __name__ == "__main__":
    m = build_system()
    set_inlet_conditions(m.fs.uv_aop_system)
    set_UV_op_conditions(m.fs.uv_aop_system)
    add_UV_scaling(m.fs.uv_aop_system)
    initialize_UV(m.fs.uv_aop_system)
    m.fs.obj = Objective(
        expr=m.fs.feed.properties[0].flow_vol
    )
    solver = get_solver()
    results = solver.solve(m)
    assert_optimal_termination(results)

    # print(f"{iscale.jacobian_cond(m.fs.uv_aop_system):.2e}")
    report_UV(m.fs.uv_aop_system, w=40)