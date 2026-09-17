extends "res://scenes/gameplay/dancer_visual_motion_v3.gd"

# Phase 7 motion tuning v4: remove the last planted-foot pauses.
# LANDING now immediately continues through the next running step instead of
# holding a support pose while the CharacterBody moves forward. RECOVERY uses a
# small visual rebound/hop before reconnecting to the accepted ballerina run.
# All motion here is local presentation only; gameplay physics remain unchanged.


func _blend_time(from_state: StringName, to_state: StringName) -> float:
	if from_state == STATE_LANDING and to_state == STATE_TRAVEL:
		return 0.02
	if from_state == STATE_STUMBLE and to_state == STATE_RECOVERY:
		return 0.04
	if from_state == STATE_RECOVERY and to_state == STATE_TRAVEL:
		return 0.03
	return super._blend_time(from_state, to_state)


func _landing_animation() -> Animation:
	# The body covers almost a metre during the 0.22 s landing gate. A planted
	# support pose therefore reads as a slide. Keep only the initial absorption
	# brief, then continue directly through brush -> opposite contact -> brush.
	# TRAVEL begins on front contact, so the final brush lands naturally into it.
	return _animation_from_poses(0.22, [0.0, 0.055, 0.125, 0.185, 0.22], [
		_landing_catch_pose(),
		_back_brush_pose(),
		_back_contact_pose(),
		_front_brush_pose(),
		_front_brush_pose(),
	], false)


func _landing_catch_pose() -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, -0.070, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.010),
		"Rig/Pelvis/Torso:rotation": _rz(-0.045),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.030),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.54),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.30),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.54),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.30),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.08),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.50),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.08),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.26),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.24),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.15),
	})


func _stumble_animation() -> Animation:
	# Keep the accepted readable disturbance, but let the legs make a catch step
	# instead of freezing underneath the torso.
	return _animation_from_poses(0.24, [0.0, 0.08, 0.16, 0.24], [
		_pose({
			"Rig/Pelvis/Torso:rotation": _rz(-0.10),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.10),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.22),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.16),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.36),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.18),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.22),
		}),
		_stumble_catch_pose(-0.050, -0.28),
		_stumble_catch_pose(-0.075, -0.38),
		_recovery_catch_pose(),
	], false)


func _stumble_catch_pose(depth: float, torso_angle: float) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.025, depth, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.12),
		"Rig/Pelvis/Torso:rotation": _rz(torso_angle),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.13),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.86),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.34),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.62),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.28),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.30),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.34),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.10),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.18),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.54),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.08),
	})


func _recovery_animation() -> Animation:
	# Phase 6 owns the exact 0.62 s recovery window. Visually use that window as
	# catch -> compress -> small rebound -> opposite contact -> run brush. The
	# rebound is deliberately small so it reads as graceful recovery, not a jump.
	return _animation_from_poses(0.62, [0.0, 0.10, 0.22, 0.36, 0.50, 0.62], [
		_recovery_catch_pose(),
		_recovery_compress_pose(),
		_recovery_hop_pose(),
		_back_contact_pose(),
		_front_brush_pose(),
		_front_brush_pose(),
	], false)


func _recovery_catch_pose() -> Dictionary:
	return _stumble_catch_pose(-0.075, -0.38)


func _recovery_compress_pose() -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.010, -0.090, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.055),
		"Rig/Pelvis/Torso:rotation": _rz(-0.17),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.07),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.42),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.31),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.42),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.31),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.16),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.58),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.12),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.12),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.56),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.12),
	})


func _recovery_hop_pose() -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, 0.052, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.018),
		"Rig/Pelvis/Torso:rotation": _rz(-0.045),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.030),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.72),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.25),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.72),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.25),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.38),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.14),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.30),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.30),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.18),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.28),
	})
