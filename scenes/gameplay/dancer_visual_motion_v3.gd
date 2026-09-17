extends "res://scenes/gameplay/dancer_visual_motion_v2.gd"

# Phase 7 motion polish: keep the accepted ballerina-run travel cycle and make
# the remaining gameplay states read as one connected dance vocabulary.
# All transforms here are local presentation only; Dancer remains the gameplay
# authority for translation, velocity, collision, jump, balance and recovery.


func _blend_time(from_state: StringName, to_state: StringName) -> float:
	# Landing and low-passage exits must reconnect quickly to the accepted run.
	# Longer generic crossfades make planted feet appear to slide while the
	# CharacterBody keeps travelling at full gameplay speed.
	if from_state == STATE_LANDING and to_state == STATE_TRAVEL:
		return 0.05
	if from_state == STATE_LOW_TRANSITION or to_state == STATE_LOW_TRANSITION:
		return 0.06
	return super._blend_time(from_state, to_state)


func _jump_animation() -> Animation:
	return _animation_from_poses(0.18, [0.0, 0.07, 0.18], [
		_pose({
			"Rig:position": Vector3(0.0, -0.070, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.060),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.035),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.28),
			"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.34),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.20),
			"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.34),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.08),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.42),
			"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.16),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.10),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.42),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.16),
		}),
		_pose({
			"Rig:position": Vector3(0.0, 0.020, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.020),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.020),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.72),
			"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.24),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.72),
			"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.24),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.24),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.16),
			"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.28),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.38),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.10),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.30),
		}),
		_pose({
			"Rig:position": Vector3(0.0, 0.035, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.010),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.015),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.90),
			"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.20),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.90),
			"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.20),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.34),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.12),
			"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.34),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.46),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.08),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.34),
		}),
	], false)


func _airborne_animation() -> Animation:
	return _animation_from_poses(0.42, [0.0, 0.20, 0.42], [
		_airborne_phrase_pose(0.035, 0.46, -0.34, 0.90),
		_airborne_phrase_pose(0.040, 0.42, -0.30, 0.96),
		_airborne_phrase_pose(0.025, 0.32, -0.22, 0.76),
	], false)


func _airborne_phrase_pose(lift: float, front_hip: float, back_hip: float, arm_open: float) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, lift, 0.0),
		"Rig/Pelvis/Torso:rotation": _rz(-0.012),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.018),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-arm_open),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.22),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(arm_open),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.22),
		"Rig/Pelvis/LegBackHip:rotation": _rz(back_hip),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.16),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.32),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(front_hip),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.12),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.34),
	})


func _landing_animation() -> Animation:
	# Keep the legs active for the full 0.22 s LANDING gate. The first frame is
	# a unilateral soft absorption; the free leg then releases behind the body
	# before the pose reconnects to the exact opening contact of the run cycle.
	# This avoids travelling forward on a frozen two-foot silhouette.
	return _animation_from_poses(0.22, [0.0, 0.07, 0.14, 0.22], [
		_landing_absorb_pose(),
		_landing_release_pose(),
		_landing_prepare_run_pose(),
		_front_contact_pose(),
	], false)


func _landing_absorb_pose() -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, -0.082, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.012),
		"Rig/Pelvis/Torso:rotation": _rz(-0.052),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.034),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.50),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.31),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.50),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.31),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.10),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.56),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.07),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.24),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.24),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.16),
	})


func _landing_release_pose() -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, -0.045, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.008),
		"Rig/Pelvis/Torso:rotation": _rz(-0.034),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.026),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.60),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.60),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.08),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.36),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.09),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.34),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.18),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.22),
	})


func _landing_prepare_run_pose() -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, -0.026, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.006),
		"Rig/Pelvis/Torso:rotation": _rz(-0.024),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.022),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.68),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.68),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.07),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.24),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.08),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.30),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.22),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.14),
	})


func _low_transition_animation() -> Animation:
	# Low transition now follows the same alternating support logic as the
	# accepted ballerina run, but without any flight phase. One complete low run
	# step keeps the silhouette travelling instead of crouching or skating.
	return _animation_from_poses(0.55, [0.0, 0.12, 0.27, 0.42, 0.55], [
		_low_front_support_pose(),
		_low_back_brush_pose(),
		_low_back_support_pose(),
		_low_front_brush_pose(),
		_low_front_support_pose(),
	], false)


func _low_front_support_pose() -> Dictionary:
	return _low_run_pose(
		-0.080,
		0.08, 0.54, -0.10,
		-0.26, 0.30, -0.14,
		-0.010
	)


func _low_back_brush_pose() -> Dictionary:
	return _low_run_pose(
		-0.115,
		-0.08, 0.34, -0.11,
		0.38, 0.24, -0.28,
		-0.006
	)


func _low_back_support_pose() -> Dictionary:
	return _low_run_pose(
		-0.130,
		-0.26, 0.30, -0.14,
		0.08, 0.54, -0.10,
		0.010
	)


func _low_front_brush_pose() -> Dictionary:
	return _low_run_pose(
		-0.110,
		0.38, 0.24, -0.28,
		-0.08, 0.34, -0.11,
		0.006
	)


func _low_run_pose(
	depth: float,
	front_hip: float,
	front_knee: float,
	front_foot: float,
	back_hip: float,
	back_knee: float,
	back_foot: float,
	breath: float
) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, depth, 0.0),
		"Rig/Pelvis:rotation": _rz(breath * 0.40),
		"Rig/Pelvis/Torso:rotation": _rz(-0.060 - breath * 0.12),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.038 + breath * 0.08),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.50 + breath),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.34),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.50 + breath),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.34),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(front_hip),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(front_knee),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(front_foot),
		"Rig/Pelvis/LegBackHip:rotation": _rz(back_hip),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(back_knee),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(back_foot),
	})


func _balance_animation() -> Animation:
	return _animation_from_poses(1.40, [0.0, 0.70, 1.40], [
		_retire_balance_pose(-0.020),
		_retire_balance_pose(0.020),
		_retire_balance_pose(-0.020),
	], true)


func _retire_balance_pose(sway: float) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, 0.015, 0.0),
		"Rig/Pelvis:rotation": _rz(sway),
		"Rig/Pelvis/Torso:rotation": _rz(-sway * 0.85),
		"Rig/Pelvis/Torso/Head:rotation": _rz(sway * 0.35),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-1.08),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.24),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(1.08),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.24),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.025),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.070),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.10),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.65),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(-1.32),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.18),
	})