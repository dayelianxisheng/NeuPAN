import unittest

from sgcf_nrmp.data.procedural.dataset_generator import split_scene_ids


class DatasetSplitTest(unittest.TestCase):
    def test_scene_level_splits_are_disjoint_and_complete(self) -> None:
        splits=split_scene_ids(100,{"train":.7,"validation":.15,"test":.15},7)
        sets={key:set(value) for key,value in splits.items()}
        self.assertFalse(sets["train"] & sets["validation"]); self.assertFalse(sets["train"] & sets["test"]); self.assertFalse(sets["validation"] & sets["test"])
        self.assertEqual(set.union(*sets.values()),set(range(100)))
        self.assertEqual([len(sets[n]) for n in ("train","validation","test")],[70,15,15])
