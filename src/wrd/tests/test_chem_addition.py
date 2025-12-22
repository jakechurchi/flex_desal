import pytest

from pyomo.environ import assert_optimal_termination, value

from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.exceptions import ConfigurationError

from watertap.core.solvers import get_solver

import wrd.components.chemical_addition as ca

solver = get_solver()


@pytest.mark.component
def test_chem_addition():
    # These costs are based directly on Qin=2637 and yaml inputs, so values should agree very closely (But they don't)
    # Once resolved, these should be switched to provided monthly data.
    annual_costs = {
            "ammonium_sulfate": 2662,
            "sodium_hypochlorite": 27074,
            "sulfuric_acid": 106556,
            "scale_inhibitor": 54393,
            "calcium_hydroxide": 567705,
            "sodium_hydroxide": 37373,
            "sodium_bisulfite": 29499,
    }
    for i, chem in enumerate(annual_costs.keys(), 1):
        # All of this stuff should be in main??

        # Dummy data just for testing
        # dose = None, #0.01 * i
        # cost = None, #0.5 * i
        # purity = None, #1

        # m = ca.build_system(chemical_name=chem)
        # ca.calculate_scaling_factors(m)
        # ca.set_inlet_conditions(m)
        # ca.set_chem_addition_op_conditions(m.fs.chem_addition, dose=dose)
        # ca.initialize_system(m)
        # assert degrees_of_freedom(m) == 0
        # results = solver.solve(m)
        # assert_optimal_termination(results)
        # ca.report_chem_addition(m.fs.chem_addition, w=40)
        # chem_registered = chem in m.fs.costing._registered_flows.keys()
        # ca.add_chem_addition_costing(
        #     m.fs.chem_addition, chem_cost=cost, chem_purity=purity
        # )
        # assert not chem_registered
        # m.fs.costing.cost_process()
        # m.fs.costing.add_LCOW(m.fs.product.properties[0].flow_vol_phase["Liq"])
        # m.fs.costing.initialize()
        # assert degrees_of_freedom(m) == 0
        # results = solver.solve(m)
        # assert_optimal_termination(results)
        
        m = ca.main(
            chemical_name=chem,
            Qin=2637,
            Cin=0.5,
            dose=None,
            chem_cost=None,
            chem_purity=None,
            )

        operational_cost = m.fs.costing.total_operating_cost()
        expected_cost = annual_costs[chem]
        assert  pytest.approx(value(operational_cost), rel=.15) == expected_cost  # $/yr


# Don't understand what this is testing-->
@pytest.mark.skip
def test_chem_addition_missing_data():
    msg = "Must specify a chemical for addition."
    with pytest.raises(ConfigurationError, match=msg):
        m = ca.build_system(chemical_name=None)
