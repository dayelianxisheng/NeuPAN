import json
from pathlib import Path
import unittest
import numpy as np
import torch

from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation


OUT=Path('sgcf_nrmp_project/artifacts/stages/stage_10_rgb_semantic_perception')


class Stage10DDiagnosticTest(unittest.TestCase):
    def test_four_images_are_train_only_fixed_and_cover_all_classes(self):
        selection=json.loads((OUT/'four_image_selection.json').read_text()); self.assertEqual(selection['split'],'train'); self.assertEqual(selection['selected_scene_ids'],[0,1,2,3]); self.assertTrue(selection['all_classes_covered']); self.assertFalse(selection['selection_changed_after_results'])
    def test_hashes_and_seed_metadata_exist(self):
        for record in json.loads((OUT/'four_image_selection.json').read_text())['records']:
            self.assertEqual(len(record['rgb_sha256']),64); self.assertEqual(len(record['semantic_label_sha256']),64); self.assertIn('geometry_seed',record); self.assertIn('appearance_seed',record); self.assertIn('camera_seed',record)
    def test_fair_comparison_and_weight_order(self):
        comparison=json.loads((OUT/'four_image_loss_comparison.json').read_text()); self.assertTrue(comparison['same_initialization']); self.assertTrue(comparison['same_steps']); audit=json.loads((OUT/'stage10d_class_weight_audit.json').read_text()); self.assertEqual(list(audit['class_order'].values()),[0,1,2,3,4]); self.assertEqual(list(audit['actual_normalized_weights']),list(audit['class_order']))
    def test_fixed_seed_initial_state_is_reproducible_and_finite(self):
        torch.manual_seed(10); a=TinySemanticSegmentation(); torch.manual_seed(10); b=TinySemanticSegmentation();
        for x,y in zip(a.parameters(),b.parameters()): self.assertTrue(torch.equal(x,y)); self.assertTrue(torch.isfinite(x).all())
    def test_crop_classifier_did_not_use_nontrain_data(self):
        result=json.loads((OUT/'human_robot_patch_separability.json').read_text()); self.assertTrue(result['uses_train_only']); self.assertLessEqual(result['parameter_count'],100000); self.assertEqual(result['training_accuracy'],1.0)


if __name__=='__main__': unittest.main()
