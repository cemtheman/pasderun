extends "res://scenes/gameplay/dancer_visual_motion_v4.gd"

# Phase 7 motion tuning v5: foot-preserving low transition.
# The previous low passage lowered the whole rig more than the articulated knees
# compensated for, so the shoes appeared to sink/shorten and the body read as
# leaning backward. Keep the pelvis drop modest, visibly flex the supporting
# knee, and carry the torso slightly forward while alternating support.
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
		0.12, 0.78, -0.05,
		-0.20, 0.42, -0.14,
		-0.010
	)


func _low_back_brush_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.075,
		-0.06, 0.58, -0.10,
		0.34, 0.36, -0.26,
		-0.006
	)


func _low_back_support_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.085,
		-0.20, 0.42, -0.14,
		0.12, 0.80, -0.05,
		0.010
	)


func _low_front_brush_pose_v5() -> Dictionary:
	return _low_articulated_pose_v5(
		-0.075,
		0.34, 0.36, -0.26,
		-0.06, 0.58, -0.10,
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
	# A small forward local shift keeps the centre of mass visually over the
	# supporting foot. Most of the apparent height reduction now comes from knee
	# articulation rather than sinking the entire rig through the floor.
	return _pose({
		"Rig:position": Vector3(0.025, depth, 0.0),
		"Rig/Pelvis:rotation": _rz(breath * 0.30),
		"Rig/Pelvis/Torso:rotation": _rz(-0.090 - breath * 0.10),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.052 + breath * 0.06),
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
