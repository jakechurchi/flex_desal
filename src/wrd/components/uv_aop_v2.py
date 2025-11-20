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
from idaes.core.surrogate.pysmo_surrogate import PysmoSurrogate

from watertap.core.solvers import get_solver
from watertap.core import Database
from watertap.unit_models.zero_order import ChemicalAdditionZO
from watertap.core.wt_database import Database
from watertap.core.zero_order_properties import WaterParameterBlock
from watertap.core.util.model_diagnostics.infeasible import *
from watertap.costing.zero_order_costing import ZeroOrderCosting
from watertap.core.util.initialization import *



def build_UV(blk, prop_package):

    blk.feed = Feed(property_package=prop_package)
    blk.product = Product(property_package=prop_package)

    blk.unit = StateJunction(property_package=prop_package)

    blk.unit.power_consumption = Var(
        initialize= 0,
        domain= NonNegativeReals,
        units= pyunits.kW,
        doc= "Power consumption of UV_aop",
    )

    power_surrogate = PysmoSurrogate.load_from_file('UV_surr_rbf_linear.json')
    blk.power_surrogate = SurrogateBlock()
    # define inputs and outputs as lists of Pyomo Var objects
    inputs = ["UV1_mgd"]
    outputs = ["UV1_kW"]
    blk.power_surrogate.build_model(power_surrogate, input_vars=inputs, output_vars=outputs)

    blk.unit.power_use = Constraint(
        Expression = blk.unit.power_consumption == blk.power_surrogate.evaluate(blk.feed.properties[0].vol_flow)
    )