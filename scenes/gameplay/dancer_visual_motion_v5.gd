extends "res://scenes/gameplay/dancer_visual_motion_v4.gd"

# Phase 7 motion tuning v5: foot-preserving low transition.
# The low passage must lower the pelvis through anatomical knee flexion rather
# than by sinking the whole rig. In this side-view hierarchy a positive hip
# angle carries the thigh/knee forward; the knee joint must then rotate in the
# opposite (negative) local direction so the shin folds back underneath the
# body. Supporting feet counter-rotate to stay close to the floor plane.
# Gameplay collider/timing remain owned by Dancer and are unchanged here.


func _low_transition_animation() -> Animation:
	return _animation_from_poses(0.55, [0.0, 0.12, 0.27, 0.42, 0.55], [
		_low_front_support_pose_v5(),
		_low_back_brush_pose_v5(),
		_low_back_support_pose_v5(),
		_low_front_brush_pose_v5(),
		_low_front_support_pose_v5(),
	], false)


func _low_front_support_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.060,
		0.38, -0.76, 0.36,
		-0.18, -0.36, 0.18,
		-0.010
	)


func _low_back_brush_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.075,
		0.42, -0.84, 0.40,
		0.34, -0.26, -0.18,
		-0.006
	)


func _low_back_support_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.085,
		-0.18, -0.36, 0.18,
		0.45, -0.90, 0.43,
		0.010
	)


func _low_front_brush_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.075,
		0.34, -0.26, -0.18,
		0.42, -0.84, 0.40,
		0.006
	)


func _low_articulated_pose_v5(
	depth: float,
	front_hip: float,
	front_knee: float,
	front_foot: float,
	back_hip: float,
	back_knee: float,
	back_foot: float,
	breath: float
) -> Dictionary:
	# Keep the centre of mass over the supporting foot. The thigh advances while
	# the shin folds back beneath it, so the pelvis can descend without shortening
	# the visible legs or producing the previous reverse-knee silhouette.
	return _pose({
		"Rig:position": Vector3(0.020, depth, 0.0),
		"Rig/Pelvis:rotation": _rz(breath * 0.30),
		"Rig/Pelvis/Torso:rotation": _rz(-0.080 - breath * 0.10),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.048 + breath * 0.06),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.48 + breath),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.36),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.48 + breath),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.36),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(front_hip),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(front_knee),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(front_foot),
		"Rig/Pelvis/LegBackHip:rotation": _rz(back_hip),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(back_knee),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(back_foot),
	})
