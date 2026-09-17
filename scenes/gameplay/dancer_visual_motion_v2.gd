extends "res://scenes/gameplay/dancer_visual.gd"

# Phase 7 motion tuning v4: reference-led ballerina run.
# This is a true alternating weight-transfer cycle rather than a walk gait or
# a repeated one-foot chasse hop. Each half-cycle has contact -> brush -> brief
# flight -> opposite contact. Dancer still owns every bit of global movement;
# this script only changes local presentation.

const RUN_CYCLE_DURATION := 0.56
const RUN_FLIGHT_LIFT := 0.048
const RUN_CONTACT_DROP := -0.018


func _travel_animation() -> Animation:
	return _animation_from_poses(
		RUN_CYCLE_DURATION,
		[0.0, 0.08, 0.14, 0.28, 0.36, 0.42, 0.56],
		[
			_front_contact_pose(),
			_back_brush_pose(),
			_back_flight_pose(),
			_back_contact_pose(),
			_front_brush_pose(),
			_front_flight_pose(),
			_front_contact_pose(),
		],
		true
	)


func _front_contact_pose() -> Dictionary:
	return _ballerina_run_pose(
		RUN_CONTACT_DROP,
		0.08, 0.18, -0.08,
		-0.28, 0.24, -0.12,
		-0.020
	)


func _back_brush_pose() -> Dictionary:
	return _ballerina_run_pose(
		0.0,
		-0.12, 0.12, -0.10,
		0.42, 0.20, -0.34,
		-0.010
	)


func _back_flight_pose() -> Dictionary:
	return _ballerina_run_pose(
		RUN_FLIGHT_LIFT,
		-0.34, 0.16, -0.16,
		0.52, 0.08, -0.38,
		0.006
	)


func _back_contact_pose() -> Dictionary:
	return _ballerina_run_pose(
		RUN_CONTACT_DROP,
		-0.28, 0.24, -0.12,
		0.08, 0.18, -0.08,
		0.020
	)


func _front_brush_pose() -> Dictionary:
	return _ballerina_run_pose(
		0.0,
		0.42, 0.20, -0.34,
		-0.12, 0.12, -0.10,
		0.010
	)


func _front_flight_pose() -> Dictionary:
	return _ballerina_run_pose(
		RUN_FLIGHT_LIFT,
		0.52, 0.08, -0.38,
		-0.34, 0.16, -0.16,
		-0.006
	)


func _ballerina_run_pose(
	lift: float,
	front_hip: float,
	front_knee: float,
	front_foot: float,
	back_hip: float,
	back_knee: float,
	back_foot: float,
	breath: float
) -> Dictionary:
	# Keep the torso carried forward and visually quiet. The run should read from
	# alternating leg/foot articulation, not from vertical bouncing or arm swing.
	return _pose({
		"Rig:position": Vector3(0.0, lift, 0.0),
		"Rig/Pelvis:rotation": _rz(breath * 0.35),
		"Rig/Pelvis/Torso:rotation": _rz(-0.018 - breath * 0.20),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.020 + breath * 0.10),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.72 + breath),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.30),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.72 + breath),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.30),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(front_hip),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(front_knee),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(front_foot),
		"Rig/Pelvis/LegBackHip:rotation": _rz(back_hip),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(back_knee),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(back_foot),
	})
