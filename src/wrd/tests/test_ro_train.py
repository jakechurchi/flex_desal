import pytest
from pyomo.environ import value, units as pyunits
from wrd.components.ro_train import main


@pytest.mark.component
def test_ro_train_main():
    m = main()
