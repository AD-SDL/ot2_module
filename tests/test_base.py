"""base for unit tests"""
import unittest


class TestOT2_Base(unittest.TestCase):
    """base ot2 test class"""

    pass


class TestImports(TestOT2_Base):
    """test importing the module"""

    def test_ot2_driver_import(self):
        """test importing the ot2 driver"""
        import ot2_driver

        assert ot2_driver.__version__


if __name__ == "__main__":
    unittest.main()
