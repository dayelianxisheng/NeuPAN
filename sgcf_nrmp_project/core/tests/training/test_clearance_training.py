import inspect
import tempfile
import unittest
from pathlib import Path

import torch

from sgcf_nrmp.models.field import LidarClearanceField
from sgcf_nrmp.training.checkpoint import load_checkpoint, save_checkpoint
from sgcf_nrmp.training.lidar_clearance_trainer import set_deterministic_seed
from sgcf_nrmp.training.losses import ClearanceLoss
from models.test_lidar_clearance_field import config, inputs


class ClearanceTrainingTest(unittest.TestCase):
    def test_single_batch_backward(self):
        model=LidarClearanceField(config()); output=model(*inputs()); loss_fn=ClearanceLoss(5.,[1,1,1,1]); target=torch.ones(2,1); collision=torch.zeros(2,1,dtype=torch.bool); category=torch.zeros(2,1,dtype=torch.int64)
        loss=loss_fn(output,target,collision,category)["total"]; loss.backward(); self.assertTrue(any(parameter.grad is not None for parameter in model.parameters()))

    def test_world_fields_are_not_loss_arguments(self):
        parameters=set(inspect.signature(ClearanceLoss.forward).parameters)
        self.assertNotIn("world_clearance",parameters); self.assertNotIn("world_collision",parameters)

    def test_hidden_world_collision_uses_observable_target_only(self):
        loss_fn=ClearanceLoss(5.,[1,1,1,1]); model=LidarClearanceField(config()); output=model(*inputs())
        # No world label is accepted; observable collision remains false.
        result=loss_fn(output,torch.ones(2,1),torch.zeros(2,1,dtype=torch.bool),torch.zeros(2,1,dtype=torch.int64))
        self.assertTrue(torch.isfinite(result["total"]))

    def test_checkpoint_model_and_optimizer_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            model=LidarClearanceField(config()); optimizer=torch.optim.Adam(model.parameters()); output=model(*inputs()); output.observable_clearance.sum().backward(); optimizer.step()
            path=Path(directory)/"state.pt"; save_checkpoint(path,model,optimizer,3,{"x":1}); expected={k:v.clone() for k,v in model.state_dict().items()}
            restored=LidarClearanceField(config()); restored_optimizer=torch.optim.Adam(restored.parameters()); state=load_checkpoint(path,restored,restored_optimizer)
            for key,value in restored.state_dict().items(): torch.testing.assert_close(value,expected[key])
            self.assertEqual(state["epoch"],3); self.assertTrue(restored_optimizer.state_dict()["state"])

    def test_fixed_seed_short_training_reproducible(self):
        def run():
            set_deterministic_seed(77); model=LidarClearanceField(config()); optimizer=torch.optim.Adam(model.parameters(),lr=.002); loss_fn=ClearanceLoss(5.,[1,1,1,1]); values=inputs(); target=torch.tensor([[.2],[1.3]]); collision=torch.zeros(2,1,dtype=torch.bool); category=torch.zeros(2,1,dtype=torch.int64)
            for _ in range(8): optimizer.zero_grad(); loss=loss_fn(model(*values),target,collision,category)["total"]; loss.backward(); optimizer.step()
            return float(loss.detach()),model(*values).observable_clearance.detach()
        loss_a,pred_a=run(); loss_b,pred_b=run(); self.assertAlmostEqual(loss_a,loss_b,places=7); torch.testing.assert_close(pred_a,pred_b)

    def test_small_synthetic_set_overfits(self):
        set_deterministic_seed(9); model=LidarClearanceField(config(False)); optimizer=torch.optim.Adam(model.parameters(),lr=.005); loss_fn=ClearanceLoss(5.,[1,1,1,1],collision_weight=0.)
        batch,n=16,180; points=torch.zeros(batch,n,2); points[:,0]=torch.tensor([2.,0.]); ranges=torch.zeros(batch,n); ranges[:,0]=2.; mask=torch.zeros(batch,n,dtype=torch.bool); mask[:,0]=True
        x=torch.linspace(-1.,1.,batch); query=torch.stack((x,torch.zeros_like(x),torch.zeros_like(x),torch.ones_like(x)),dim=-1); target=(2.-x-.4).reshape(-1,1); collision=torch.zeros(batch,1,dtype=torch.bool); category=torch.zeros(batch,1,dtype=torch.int64)
        initial=None
        for _ in range(160):
            optimizer.zero_grad(); loss=loss_fn(model(points,ranges,mask,query),target,collision,category)["total"]; loss.backward(); optimizer.step(); initial=float(loss.detach()) if initial is None else initial
        self.assertLess(float(loss.detach()),initial*.15)
