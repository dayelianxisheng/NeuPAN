"""Stage 01 package import checks."""

import unittest

import sgcf_nrmp


class ImportTest(unittest.TestCase):
    def test_version_is_exposed(self) -> None:
        self.assertEqual(sgcf_nrmp.__version__, "0.1.0.dev0")


if __name__ == "__main__":
    unittest.main()
