from pyomo.environ import (
    ConcreteModel,
    Reals,
    TransformationFactory,
    assert_optimal_termination,
    value,
    units as pyunits,
)
from idaes.core.util.model_statistics import degrees_of_freedom
from pyomo.network import Arc

from idaes.core.util.constants import Constants
from idaes.core import FlowsheetBlock, UnitModelCostingBlock
from idaes.core.util.initialization import propagate_state
from idaes.models.unit_models import StateJunction, Feed, Product
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.scaling import calculate_scaling_factors, set_scaling_factor

from watertap.costing import WaterTAPCosting
from watertap.property_models.NaCl_T_dep_prop_pack import NaClParameterBlock
from watertap.core.solvers import get_solver

from wrd.utilities import load_config, get_config_value, get_config_file
from srp.utils import touch_flow_and_conc
from models.pump_detailed import PumpDetailed, Efficiency, PumpCurveDataType

__all__ = [
    "build_pump",
    "initialize_pump",
    "set_pump_op_conditions",
    "report_pump",
    "add_pump_scaling",
    "add_pump_costing",
]

solver = get_solver()


def build_system(stage_num=1, file="wrd_inputs_8_19_21.yaml", uf=False):
    m = ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    m.fs.properties = NaClParameterBlock()
    m.fs.costing = WaterTAPCosting()

    m.fs.feed = Feed(property_package=m.fs.properties)
    touch_flow_and_conc(m.fs.feed)
    m.fs.pump = FlowsheetBlock(dynamic=False)
    build_pump(
        m.fs.pump,
        stage_num=stage_num,
        file=file,
        prop_package=m.fs.properties,
        uf=uf,
    )

    m.fs.product = Product(property_package=m.fs.properties)
    touch_flow_and_conc(m.fs.product)

    # Arcs to connect the unit models
    m.fs.feed_to_pump = Arc(
        source=m.fs.feed.outlet,
        destination=m.fs.pump.feed.inlet,
    )
    m.fs.pump_to_product = Arc(
        source=m.fs.pump.product.outlet,
        destination=m.fs.product.inlet,
    )

    TransformationFactory("network.expand_arcs").apply_to(m)

    m.fs.properties.set_default_scaling(
        "flow_mass_phase_comp", 1e-1, index=("Liq", "H2O")
    )
    m.fs.properties.set_default_scaling(
        "flow_mass_phase_comp", 1e2, index=("Liq", "NaCl")
    )

    return m


def build_pump(
    blk,
    stage_num=1,
    file="wrd_inputs_8_19_21.yaml",
    prop_package=None,
    uf=False,
):

    if prop_package is None:
        m = blk.model()
        prop_package = m.fs.ro_properties

    blk.config_data = load_config(get_config_file(file))
    blk.stage_num = stage_num
    blk.uf = uf
    blk.feed = StateJunction(property_package=prop_package)
    touch_flow_and_conc(blk.feed)
    density = 1000 * pyunits.kg / pyunits.m**3

    if stage_num == 3:
        # use constant efficiency for TSRO pump
        blk.unit = PumpDetailed(
            property_package=prop_package,
            variable_efficiency=Efficiency.Fixed,
        )
        # Assuming constant 50% efficiency for TSRO pump
        blk.unit.efficiency_pump.fix(0.50)

    else:
        if blk.uf == True:
            # Checked these are correct from data in src/models/tests
            head_surrogate_coeffs = {0: 98.74, 1: -123.07, 2: 442.0, 3: -1920.0}
            efficiency_surrogate_coeffs = {0: 0.0677, 1: 5.357, 2: -4.475, 3: -19.578}
            geometric_head = pyunits.convert(
                12 * pyunits.psi / (density * Constants.acceleration_gravity),
                to_units=pyunits.m,
            )

        elif stage_num == 1:
            head_surrogate_coeffs = {0: 114.22, 1: -410.6, 2: 2729.2, 3: -8089.1}
            efficiency_surrogate_coeffs = {0: 0.389, 1: -0.535, 2: 41.373, 3: -138.82}
            geometric_head = pyunits.convert(
                0 * pyunits.psi / (density * Constants.acceleration_gravity),
                to_units=pyunits.m,
            )

        elif stage_num == 2:
            # Checked these are correct from data in src/models/tests
            head_surrogate_coeffs = {0: 30.51, 1: -41.90, 2: 1015.7, 3: -23998.64}
            efficiency_surrogate_coeffs = {0: 0.071, 1: 20.72, 2: -124.82, 3: -280.32}
            geometric_head = pyunits.convert(
                0 * pyunits.psi / (density * Constants.acceleration_gravity),
                to_units=pyunits.m,
            )

        blk.unit = PumpDetailed(
            property_package=prop_package,
            variable_efficiency=Efficiency.Flow,
            pump_curve_data_type=PumpCurveDataType.SurrogateCoefficent,
            head_surrogate_coeffs=head_surrogate_coeffs,
            efficiency_surrogate_coeffs=efficiency_surrogate_coeffs,
        )
        blk.unit.ref_speed_fraction.fix(1.0)
        blk.unit.system_curve_geometric_head.fix(geometric_head)

    blk.product = StateJunction(property_package=prop_package)

    # Add Arcs
    blk.feed_to_unit = Arc(source=blk.feed.outlet, destination=blk.unit.inlet)
    blk.unit_to_product = Arc(source=blk.unit.outlet, destination=blk.product.inlet)

    TransformationFactory("network.expand_arcs").apply_to(blk)


def set_pump_op_conditions(blk):
    if blk.uf:
        # All the pumps are assumed to have the same outlet pressure for UF pumps because they collect in a header
        Pout = get_config_value(
            blk.config_data, "pump_outlet_pressure", "uf_pumps", f"pump"
        )
    else:
        Pout = get_config_value(
            blk.config_data,
            "pump_outlet_pressure",
            "ro_pumps",
            f"pump_stage_{blk.stage_num}",
        )
        print(
            f"Setting pump {blk.stage_num} operating conditions, Pout = {value(Pout)} psi"
        )
    blk.unit.control_volume.properties_out[0].pressure.fix(Pout)


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


def add_pump_scaling(blk):
    set_scaling_factor(blk.unit.work_mechanical[0], 1e-3)


def initialize_system(m):
    if m.fs.pump.uf:
        # Allow negative suction pressure for UF configuration
        m.fs.feed.properties[0].pressure.setlb(None)
        m.fs.feed.properties[0].pressure.domain = Reals
        m.fs.pump.feed.properties[0].pressure.setlb(None)
        m.fs.pump.feed.properties[0].pressure.domain = Reals

        # Change the bounds for the pump inlet pressure
        m.fs.pump.unit.control_volume.properties_in[0].pressure.setlb(None)
        m.fs.pump.unit.control_volume.properties_in[0].pressure.domain = Reals

    m.fs.feed.initialize()
    propagate_state(m.fs.feed_to_pump)
    initialize_pump(m.fs.pump)

    propagate_state(m.fs.pump_to_product)
    m.fs.product.initialize()


def initialize_pump(blk):
    blk.feed.initialize()
    propagate_state(blk.feed_to_unit)

    try:
        blk.unit.initialize()
    except:
        blk.unit.design_speed_fraction.bounds = (0, 1.1)
        blk.unit.initialize()

    propagate_state(blk.unit_to_product)
    blk.product.initialize()


def add_pump_costing(blk, costing_package=None):

    if costing_package is None:
        m = blk.model()
        costing_package = m.fs.costing

    blk.unit.costing = UnitModelCostingBlock(flowsheet_costing_block=costing_package)
    # Only want to cost opex (electricity)
    costing_package.high_pressure_pump.cost.fix(0)


def report_pump(blk, w=30, add_costing=False):
    title = "Pump Report"
    side = int(((3 * w) - len(title)) / 2) - 1
    header = "=" * side + f" {title} " + "=" * side
    print(f"\n{header}\n")
    print(f'{"Parameter":<{w}s}{"Value":<{w}s}{"Units":<{w}s}')
    print(f"{'-' * (3 * w)}")

    flow_in = blk.feed.properties[0].flow_vol_phase["Liq"]
    work = blk.unit.work_mechanical[0]
    pin = blk.unit.control_volume.properties_in[0].pressure
    deltaP = blk.unit.deltaP[0]
    pout = blk.unit.control_volume.properties_out[0].pressure

    print(
        f'{f"Inlet Flow":<{w}s}{value(pyunits.convert(flow_in, to_units=pyunits.gallons /pyunits.minute)):<{w}.3f}{"gpm"}'
    )
    print(
        f'{f"Inlet Pressure":<{w}s}{value(pyunits.convert(pin, to_units=pyunits.psi)):<{w}.3f}{"psi"}'
    )
    if hasattr(blk.unit, "system_curve_geometric_head"):
        print(
            f'{f"Evavation Change (m)":<{w}s}{value(blk.unit.system_curve_geometric_head):<{w}.3f}{"m"}'
        )
    print(
        f'{f"∆P (psi)":<{w}s}{value(pyunits.convert(deltaP, to_units=pyunits.psi)):<{w}.3f}{"psi"}'
    )
    if hasattr(blk.unit, "design_head"):
        print(
            f'{f"Design Head (m)":<{w}s}{value(pyunits.convert(blk.unit.design_head, to_units=pyunits.m)):<{w}.3f}{"m"}'
        )
    print(
        f'{f"Outlet Pressure (psi)":<{w}s}{value(pyunits.convert(pout, to_units=pyunits.psi)):<{w}.3f}{"psi"}'
    )
    print(
        f'{f"Work Mech. (kW)":<{w}s}{value(pyunits.convert(work, to_units=pyunits.kW)):<{w}.3f}{"kW"}'
    )
    print(f'{f"Efficiency (-)":<{w}s}{value(blk.unit.efficiency_pump[0]):<{w}.3f}{"-"}')
    if hasattr(blk.unit, "design_speed_fraction"):
        print(
            f'{f"Speed Ratio (-)":<{w}s}{value(blk.unit.design_speed_fraction):<{w}.3f}{"-"}'
        )

    if add_costing:
        m = blk.model()
        # Is SEC not appearing on m.fs.costing.display a known issue?
        SEC = m.fs.costing.SEC
        print(
            f'{f"Specific Energy (SEC)":<{w}s}{value(pyunits.convert(SEC, to_units=pyunits.kWh / pyunits.m**3)):<{w}.3f}{"kWh/m3"}'
        )


def main(
    Qin=2637,
    Cin=0.5,
    Tin=302,
    Pin=101325,
    stage_num=1,
    uf=False,
    file="wrd_inputs_8_19_21.yaml",
    add_costing=True,
):

    m = build_system(stage_num=stage_num, file=file, uf=uf)
    add_pump_scaling(m.fs.pump)
    calculate_scaling_factors(m)
    set_inlet_conditions(m, Qin=Qin, Cin=Cin, Tin=Tin, Pin=Pin)
    set_pump_op_conditions(m.fs.pump)

    if add_costing:
        add_pump_costing(m.fs.pump)
        m.fs.costing.cost_process()
        m.fs.costing.add_LCOW(m.fs.product.properties[0].flow_vol_phase["Liq"])
        m.fs.costing.add_specific_energy_consumption(
            m.fs.product.properties[0].flow_vol_phase["Liq"],
            name="SEC",
        )

    initialize_system(m)
    assert degrees_of_freedom(m) == 0
    results = solver.solve(m)
    try:
        assert_optimal_termination(results)
    except Exception as e:
        if uf:
            e.args = (
                "Check initial flowrate guess is reasonable as solver did not find an optimal solution with head and speed fixed."
                + str(e),
            )
        raise
    report_pump(m.fs.pump, add_costing=add_costing)

    return m


if __name__ == "__main__":
    # August 19, 2021 Data
    # Stage 1
    # for pin in [35.4]:  # [10, 15, 20, 25, 30,35, 40]:
    #     m = main(Pin=pin * pyunits.psi, stage_num=1, file="wrd_inputs_8_19_21.yaml")
    # Just testing to see what happens with an elevation change
    #     m.fs.pump.unit.system_curve_geometric_head.fix(10)
    #     m.fs.pump.unit.design_speed_fraction.bounds = (0, 1.05)
    #     # m.fs.pump.unit.control_volume.properties_out[0].pressure.unfix()
    #     # m.fs.pump.unit.design_speed_fraction.fix(.99)
    #     results = solver.solve(m)
    #     assert_optimal_termination(results)
    #     report_pump(m.fs.pump, add_costing=True)

    # # Stage 2
    # m = main(Qin=1029, Pin=125 * pyunits.psi, stage_num=2)

    # # Stage 3
    # m = main(Qin=384, Pin=(112.6 - 41.9) * pyunits.psi, stage_num=3)

    # UF pump
    # Now instead of a negative pressure due to the elevation change, the elevation change is already included and the inlet pressure is 1 atm (or for gage pressure = 0)
    m = main(
        Qin=4208,
        Pin=1e-8 * pyunits.psi,
        stage_num=1,
        uf=True,
    )

    # m.fs.pump.unit.control_volume.properties_out[0].pressure.unfix()
    # m.fs.pump.unit.design_speed_fraction.fix(.91)
    m.fs.pump.unit.system_curve_geometric_head.fix(-3.5)
    results = solver.solve(m)
    assert_optimal_termination(results)
    report_pump(m.fs.pump, add_costing=True)
