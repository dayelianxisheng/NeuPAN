import unittest,numpy as np,inspect
from sgcf_nrmp.semantic.explicit_failure_gate import explicit_failure_reliability
class GateTest(unittest.TestCase):
 def test_failures(self):
  p=np.eye(5)[[2,0]]; self.assertTrue(np.array_equal(explicit_failure_reliability(p,[1,1],False,0),[0,0])); self.assertTrue(np.array_equal(explicit_failure_reliability(p,[1,1],True,.5),[0,0])); self.assertTrue(np.array_equal(explicit_failure_reliability(p,[0,1],True,0),[0,0]))
 def test_no_forbidden_inputs(self):
  n=inspect.signature(explicit_failure_reliability).parameters; self.assertNotIn('world',n); self.assertNotIn('gt_class',n); self.assertNotIn('translation_error',n)
