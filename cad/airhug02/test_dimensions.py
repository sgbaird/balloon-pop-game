"""Numerical checks; these do not validate the physical camera dimensions."""

import unittest

import numpy as np
from scipy.spatial.transform import Rotation

from fit_dimensions import distances, fit, project, rim
from audit_photos import ruler


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


class PhotoRulerMathTests(unittest.TestCase):
    def test_rotated_projective_ruler_recovers_unseen_endpoints(self):
        # Independent forward homography on a tilted line, including an offset.
        # Test endpoints are between the annotated ticks, not used for fitting.
        mm = np.arange(30, 101, 10, dtype=float)
        axis = np.array([np.cos(0.37), np.sin(0.37)])

        def pixels(values):
            position = (12 * values + 800) / (0.002 * values + 1)
            return np.array([130, 210]) + position[:, None] * axis

        read, _, _, report = ruler(np.c_[mm, pixels(mm)])
        np.testing.assert_allclose(read(pixels(np.array([36.5, 92.25]))),
                                   [36.5, 92.25], atol=1e-7)
        self.assertLess(report["tick_rms_mm"], 1e-7)
        self.assertLess(max(abs(x) for x in report["leave_one_tick_out_error_mm"]), 1e-7)

    def test_affine_ruler_with_vertical_image_axis(self):
        mm = np.arange(20, 81, 10, dtype=float)
        points = np.c_[np.full_like(mm, 240), 900 - 8 * mm]
        read, _, _, _ = ruler(np.c_[mm, points])
        np.testing.assert_allclose(read([[240, 900 - 8 * 23], [240, 900 - 8 * 74]]),
                                   [23, 74], atol=1e-7)


if __name__ == "__main__":
    unittest.main()
