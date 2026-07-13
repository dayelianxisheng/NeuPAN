import unittest,numpy as np
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
class ProviderTest(unittest.TestCase):
 def test_gate_and_bounds(self):
  p=np.eye(5)[[2,1]]; normal=SemanticMarginProvider([[1,0],[.8,0]],p,[1,1]); drop=SemanticMarginProvider([[1,0],[.8,0]],p,[1,1],image_available=False); q=np.zeros((1,3)); self.assertTrue(0<=normal.query_margins(q)[0]<=.35); self.assertEqual(drop.query_margins(q)[0],0)
 def test_stale_unknown_padding(self):
  p=np.eye(5)[[2,0]]; x=SemanticMarginProvider([[1,0],[2,0]],p,[1,1],observable_valid=[1,0],image_age_s=.5); self.assertEqual(x.query_margins(np.zeros((1,3)))[0],0)
