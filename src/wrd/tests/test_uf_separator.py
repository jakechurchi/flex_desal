import pytest

from wrd.components.UF_separator import main


@pytest.mark.component
def test_uf_separator():
    _ = main()
