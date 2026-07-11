import unittest

import torch

from sgcf_nrmp.models.field import LidarClearanceField
from sgcf_nrmp.models.lidar.query_transform import points_in_query_frame, query_gradient_to_xyyaw


def config(collision=True):
    return {"point_hidden_dims":[16,24],"decoder_hidden_dims":[24,16],"use_max_pool":True,"use_mean_pool":True,"use_collision_head":collision,"clearance_clip_m":5.}


def inputs(batch=2,points=180):
    torch.manual_seed(1); xy=torch.randn(batch,points,2); ranges=torch.linalg.norm(xy,dim=-1); mask=torch.ones(batch,points,dtype=torch.bool); query=torch.tensor([[.2,-.1,0.,1.]]).repeat(batch,1); return xy,ranges,mask,query


class LidarClearanceFieldTest(unittest.TestCase):
    def test_shapes_for_supported_n_and_batch_one(self):
        model=LidarClearanceField(config())
        for n in (180,256,360):
            output=model(*inputs(1,n)); self.assertEqual(output.observable_clearance.shape,(1,1)); self.assertEqual(output.observable_collision_logit.shape,(1,1))

    def test_all_and_partial_padding_are_finite(self):
        model=LidarClearanceField(config())
        xy,ranges,mask,query=inputs(); mask[0]=False; mask[1,30:]=False
        output=model(xy,ranges,mask,query); self.assertTrue(torch.isfinite(output.observable_clearance).all())

    def test_masked_values_do_not_affect_output(self):
        model=LidarClearanceField(config()).eval(); xy,ranges,mask,query=inputs(); mask[:,20:]=False
        first=model(xy,ranges,mask,query).observable_clearance; xy[:,20:]=999; ranges[:,20:]=999
        second=model(xy,ranges,mask,query).observable_clearance; torch.testing.assert_close(first,second)

    def test_query_transform_known_value(self):
        points=torch.tensor([[[2.,1.]]]); query=torch.tensor([[1.,1.,1.,0.]])
        torch.testing.assert_close(points_in_query_frame(points,query),torch.tensor([[[0.,-1.]]]))

    def test_yaw_periodicity_representation(self):
        model=LidarClearanceField(config()).eval(); xy,ranges,mask,query=inputs(1)
        a=model(xy,ranges,mask,query).observable_clearance
        yaw=torch.tensor(2*torch.pi); query[:,2]=torch.sin(yaw); query[:,3]=torch.cos(yaw)
        b=model(xy,ranges,mask,query).observable_clearance; torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-6)

    def test_distance_nonnegative_and_bounded(self):
        output=LidarClearanceField(config())(*inputs()); self.assertTrue(torch.all(output.observable_clearance>=0)); self.assertTrue(torch.all(output.observable_clearance<=5))

    def test_autograd_query_gradient_shape_and_nonzero(self):
        model=LidarClearanceField(config()); xy,ranges,mask,query=inputs(); query.requires_grad_(True)
        prediction=model(xy,ranges,mask,query).observable_clearance; gradient=torch.autograd.grad(prediction.sum(),query)[0]; physical=query_gradient_to_xyyaw(gradient,query)
        self.assertEqual(gradient.shape,(2,4)); self.assertEqual(physical.shape,(2,3)); self.assertGreater(float(torch.linalg.norm(physical).detach()),0.)

    def test_autograd_matches_model_finite_difference_for_x(self):
        smooth_config=config(); smooth_config["use_max_pool"]=False
        model=LidarClearanceField(smooth_config).eval(); xy,ranges,mask,query=inputs(1); query.requires_grad_(True); value=model(xy,ranges,mask,query).observable_clearance; gradient=torch.autograd.grad(value.sum(),query)[0][0,0]
        # Mean-only pooling avoids a genuine max-pool branch switch at the query.
        epsilon=1e-2; plus=query.detach().clone(); minus=query.detach().clone(); plus[0,0]+=epsilon; minus[0,0]-=epsilon
        numerical=(model(xy,ranges,mask,plus).observable_clearance-model(xy,ranges,mask,minus).observable_clearance)/(2*epsilon)
        torch.testing.assert_close(gradient,numerical.squeeze(),atol=2e-3,rtol=2e-3)

    def test_eval_is_repeatable_and_cpu(self):
        model=LidarClearanceField(config()).eval(); values=inputs(); a=model(*values).observable_clearance; b=model(*values).observable_clearance
        torch.testing.assert_close(a,b); self.assertEqual(a.device.type,"cpu")

    def test_collision_head_can_be_disabled(self):
        output=LidarClearanceField(config(False))(*inputs()); self.assertIsNone(output.observable_collision_logit)
