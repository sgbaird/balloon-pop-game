"""Numerical checks; these do not validate the physical camera dimensions."""

import unittest

import numpy as np
from scipy.spatial.transform import Rotation

from fit_dimensions import distances, fit, project, rim


class DimensionMathTests(unittest.TestCase):
    def test_continuous_segment_distance(self):
        square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], float)
        residual = distances([[4, 0], [12, 6]], square).reshape(-1, 2)
        np.testing.assert_allclose(residual, [[0, 0], [2, 0]], atol=1e-10)

    def test_joint_shape_recovery_from_synthetic_views(self):
        frames = []
        poses = []
        for i, angles in enumerate([[25, 15, 35], [-35, 20, 80], [55, -30, -15]]):
            pose = np.r_[
                Rotation.from_euler("xyz", angles, degrees=True).as_rotvec(),
                [i * 10, 5, 250 + i * 35],
            ]
            poses.append(pose)
            frames.append(
                dict(
                    second=100 + i,
                    rear=project(rim(16), pose, 1400)[::3].tolist(),
                    front=project(rim(16, 24), pose, 1400)[::3].tolist(),
                )
            )
        seed = np.r_[15.5, 23, np.concatenate(poses)]
        result, errors = fit(frames, 1400, start=seed)
        np.testing.assert_allclose(result[:2], [16, 24], atol=0.03)
        self.assertLess(max(errors), 0.01)

    def test_fixed_shape_is_preserved(self):
        pose = np.array([0.3, 0.1, 0.8, 0, 5, 250])
        frame = dict(
            second=100,
            rear=project(rim(16), pose, 1400)[::3].tolist(),
            front=project(rim(16, 24), pose, 1400)[::3].tolist(),
        )
        result, errors = fit([frame], 1400, fixed=[16, 24], start=np.r_[12, 8, pose])
        np.testing.assert_array_equal(result[:2], [16, 24])
        self.assertLess(errors[0], 1e-6)


if __name__ == "__main__":
    unittest.main()
