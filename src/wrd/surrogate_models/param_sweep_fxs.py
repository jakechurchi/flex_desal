from watertap.core.solvers import get_solver
from parameter_sweep import LinearSample, get_sweep_params_from_yaml
from wrd.components.ro_train import *
from pyomo.environ import value, solve, ConcreteModel, TransformationFactory, units as pyunits
from pyomo.network import Arc
from srp.utils import touch_flow_and_conc
from idaes.models.unit_models import (
    Feed,
    Product,
)
from idaes.core import FlowsheetBlock
from watertap.property_models.NaCl_T_dep_prop_pack import NaClParameterBlock
from idaes.core.util.scaling import calculate_scaling_factors
from idaes.core.util.initialization import propagate_state
from idaes.core.util.model_statistics import degrees_of_freedom

# Build flowsheet function
def build_flowsheet(op_limts=None):
    m = ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    m.fs.properties = NaClParameterBlock()

    m.fs.feed = Feed(property_package=m.fs.properties)
    touch_flow_and_conc(m.fs.feed)

    m.fs.ro_train = FlowsheetBlock(dynamic=False)
    build_ro_train(
        m.fs.ro_train,
        num_stages=3,
        prop_package=m.fs.properties,
        file="wrd_inputs_8_19_21.yaml",
    )

    m.fs.product = Product(property_package=m.fs.properties)
    touch_flow_and_conc(m.fs.product)
    m.fs.brine = Product(property_package=m.fs.properties)
    touch_flow_and_conc(m.fs.brine)

    # Arcs to connect the unit models
    m.fs.feed_to_train = Arc(
        source=m.fs.feed.outlet,
        destination=m.fs.ro_train.feed.inlet,
    )
    m.fs.train_to_product = Arc(
        source=m.fs.ro_train.product.outlet,
        destination=m.fs.product.inlet,
    )
    m.fs.train_to_brine = Arc(
        source=m.fs.ro_train.disposal.outlet,
        destination=m.fs.brine.inlet,
    )

    TransformationFactory("network.expand_arcs").apply_to(m)

    m.fs.properties.set_default_scaling(
        "flow_mass_phase_comp", 1e-1, index=("Liq", "H2O")  # changed from 1
    )
    m.fs.properties.set_default_scaling(
        "flow_mass_phase_comp", 1e2, index=("Liq", "NaCl")
    )

    set_ro_train_scaling(m.fs.ro_train)
    calculate_scaling_factors(m)

    # Set feed and operational conditions
    m.fs.feed.properties.calculate_state(
    var_args={
        ("flow_vol_phase", ("Liq")): 2650 * pyunits.gallons / pyunits.minute,
        ("conc_mass_phase_comp", ("Liq", "NaCl")): 0.5 * pyunits.g / pyunits.L,
        ("pressure", None): 35.4 * pyunits.psi,
        ("temperature", None): 298.15 * pyunits.K,
    },
    hold_state=True,
    )
    set_ro_train_op_conditions(m.fs.ro_train)
    # Set limits on each stage recovery and flowrate
    for i in m.fs.ro_train.stages:
        m.fs.ro_train.stage[i].recovery_vol_phase[0, "Liq"].setlb(op_limts[f"Stage {i}"]["RR_min"])
        m.fs.ro_train.stage[i].recovery_vol_phase[0, "Liq"].setub(op_limts[f"Stage {i}"]["RR_max"])
        m.fs.ro_train.stage[i].feed.properties[0].flow_vol_phase["Liq"].setlb(
            op_limts[f"Stage {i}"]["Qin_min"]
        )
        m.fs.ro_train.stage[i].feed.properties[0].flow_vol_phase["Liq"].setub(
            op_limts[f"Stage {i}"]["Qin_max"]
        )
    # Initialize system
    assert degrees_of_freedom(m) == 0
    m.fs.feed.initialize()
    propagate_state(m.fs.feed_to_train)
    initialize_ro_train(m.fs.ro_train)
    propagate_state(m.fs.train_to_product)
    m.fs.product.initialize()
    propagate_state(m.fs.train_to_brine)
    m.fs.brine.initialize()


# Build sweep parameters function
def build_sweep_params(
    m,
    num_samples=10,
    var_lims=None,
    scenario=None,
):
    sweep_params = {}
    if scenario == "default":
        sweep_params["Recovery"] = LinearSample(
            m.fs.ro_train.recovery_vol,
            var_lims["RR_lb"],
            var_lims["RR_ub"],
            num_samples,
        )

        sweep_params["Feed Flow"] = LinearSample(
            m.fs.ro_train.feed.properties_in[0].flow_vol_phase["Liq"],
            var_lims["Qin_lb"],
            var_lims["Qin_ub"],
            num_samples,
        )
    else:
        raise KeyError(
            f"Scenario {scenario} not recognized. Please choose from: 'default'"
        )
    return sweep_params


# Optimizaiton function
def optimize(m, solver=None, check_termination=True):
    # --solve---
    return solve(m, solver=solver, check_termination=check_termination)


def build_outputs(m):
    outputs = {}
    # RR and Flows
    outputs["Stage1 RR"] = m.fs.ro_train.stage[1].recovery_vol_phase[0, "Liq"]
    outputs["Stage2 RR"] = m.fs.ro_train.stage[2].recovery_vol_phase[0, "Liq"]
    outputs["Stage3 RR"] = m.fs.ro_train.stage[3].recovery_vol_phase[0, "Liq"]
    outputs["Stage1 Qin"] = m.fs.ro_train.stage[1].feed.properties[0].flow_vol_phase["Liq"] # This is an input
    outputs["Stage2 Qin"] = m.fs.ro_train.stage[2].feed.properties[0].flow_vol_phase["Liq"]
    outputs["Stage3 Qin"] = m.fs.ro_train.stage[3].feed.properties[0].flow_vol_phase["Liq"]
    # Pressures
    outputs["Stage1 Pin"] = m.fs.ro_train.stage[1].pump.unit.control_volume.properties_in[0].pressure
    outputs["Stage2 Pin"] = m.fs.ro_train.stage[2].pump.unit.control_volume.properties_in[0].pressure
    outputs["Stage3 Pin"] = m.fs.ro_train.stage[3].pump.unit.control_volume.properties_in[0].pressure
    outputs["Stage1 Pout"] = m.fs.ro_train.stage[1].pump.unit.control_volume.properties_out[0].pressure
    outputs["Stage2 Pout"] = m.fs.ro_train.stage[2].pump.unit.control_volume.properties_out[0].pressure
    outputs["Stage3 Pout"] = m.fs.ro_train.stage[3].pump.unit.control_volume.properties_out[0].pressure
    # Powers
    outputs["Total Power"] = m.fs.ro_train.total_pump_power
    outputs["Stage1 Power"] = m.fs.ro_train.stage[1].pump.unit.work_mechanical[0]
    outputs["Stage2 Power"] = m.fs.ro_train.stage[2].pump.unit.work_mechanical[0]
    outputs["Stage3 Power"] = m.fs.ro_train.stage[3].pump.unit.work_mechanical[0]
    # Other
    outputs["Stage1 Peak Flux"] = m.fs.ro_train.stage[1].unit.first_elem_prod
    outputs["Stage2 Peak Flux"] = m.fs.ro_train.stage[2].unit.first_elem_prod
    outputs["Stage3 Peak Flux"] = m.fs.ro_train.stage[3].unit.first_elem_prod
    outputs["Stage1 Perm. Conc."] = m.fs.ro_train.stage[1].unit.mixed_permeate[0].conc_mass_phase_comp["Liq", "NaCl"]
    outputs["Stage2 Perm. Conc."] = m.fs.ro_train.stage[2].unit.mixed_permeate[0].conc_mass_phase_comp["Liq", "NaCl"]
    outputs["Stage3 Perm. Conc."] = m.fs.ro_train.stage[3].unit.mixed_permeate[0].conc_mass_phase_comp["Liq", "NaCl"]
    
    return outputs

