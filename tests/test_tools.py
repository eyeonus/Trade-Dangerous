import pytest       # noqa: F401

from tradedangerous import tools
from .helpers import copy_fixtures


def setup_module():
    copy_fixtures()


class TestTools:
    def test_derp(self, capsys):
        tools.test_derp()
