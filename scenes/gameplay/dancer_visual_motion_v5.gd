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


# Pas de Run is an always-run game. BALANCE remains a gameplay condition that
# adds Z-axis drift/recentering, but it must never replace locomotion with a
# stationary retiré pose. Keep the semantic BALANCE state for diagnostics and
# input priority while presenting the same travelling cycle as normal running.
func _balance_animation() -> Animation:
	return _travel_animation()


# Phase 9 musical choreography: the world keeps travelling at the accepted
# gameplay speed, while grounded presentation changes phrase shape. Physical
# gameplay states (jump, airborne, landing, low transition, balance, stumble)
# still have priority in dancer_visual.gd.


func _music_flow_animation() -> Animation:
	return _travel_animation()


func _music_build_animation() -> Animation:
	return _animation_from_poses(1.856, [0.0, 0.464, 0.928, 1.392, 1.856], [
		_music_pose(_front_contact_pose(), 0.52, -0.010, 0.000),
		_music_pose(_back_contact_pose(), 0.66, -0.020, 0.010),
		_music_pose(_front_contact_pose(), 0.80, -0.030, 0.020),
		_music_pose(_back_contact_pose(), 0.94, -0.040, 0.032),
		_music_pose(_front_contact_pose(), 1.02, -0.045, 0.040),
	], true)


func _music_release_animation() -> Animation:
	return _animation_from_poses(1.856, [0.0, 0.464, 0.928, 1.392, 1.856], [
		_music_pose(_front_contact_pose(), 0.94, -0.020, 0.020),
		_music_pose(_back_contact_pose(), 0.82, -0.010, 0.010),
		_music_pose(_front_contact_pose(), 0.70, 0.000, 0.000),
		_music_pose(_back_contact_pose(), 0.58, 0.018, -0.010),
		_music_pose(_front_contact_pose(), 0.50, 0.030, -0.018),
	], true)


func _music_pulse_animation() -> Animation:
	return _animation_from_poses(1.856, [0.0, 0.232, 0.464, 0.696, 0.928, 1.160, 1.392, 1.624, 1.856], [
		_music_pose(_front_contact_pose(), 0.96, -0.025, 0.028),
		_music_pose(_back_brush_pose(), 0.52, 0.015, -0.008),
		_music_pose(_back_contact_pose(), 0.96, -0.025, 0.028),
		_music_pose(_front_brush_pose(), 0.52, 0.015, -0.008),
		_music_pose(_front_contact_pose(), 0.96, -0.025, 0.028),
		_music_pose(_back_brush_pose(), 0.52, 0.015, -0.008),
		_music_pose(_back_contact_pose(), 0.96, -0.025, 0.028),
		_music_pose(_front_brush_pose(), 0.52, 0.015, -0.008),
		_music_pose(_front_contact_pose(), 0.96, -0.025, 0.028),
	], true)


func _music_climax_animation() -> Animation:
	return _animation_from_poses(0.928, [0.0, 0.232, 0.464, 0.696, 0.928], [
		_music_pose(_front_contact_pose(), 0.90, -0.030, 0.025),
		_music_pose(_back_flight_pose(), 1.08, -0.045, 0.060),
		_music_pose(_back_contact_pose(), 1.14, -0.050, 0.070),
		_music_pose(_front_flight_pose(), 1.08, -0.045, 0.060),
		_music_pose(_front_contact_pose(), 0.90, -0.030, 0.025),
	], true)


func _music_prep_animation() -> Animation:
	return _animation_from_poses(0.75, [0.0, 0.25, 0.50, 0.75], [
		_music_pose(_front_contact_pose(), 0.64, -0.025, 0.000),
		_music_pose(_back_brush_pose(), 0.48, -0.055, -0.015),
		_music_pose(_front_contact_pose(), 0.38, -0.085, -0.045),
		_music_pose(_recovery_compress_pose(), 0.30, -0.105, -0.060),
	], false)


func _music_accent_animation() -> Animation:
	return _animation_from_poses(0.22, [0.0, 0.08, 0.16, 0.22], [
		_music_pose(_front_contact_pose(), 0.70, -0.020, 0.000),
		_music_pose(_back_flight_pose(), 1.18, -0.055, 0.075),
		_music_pose(_front_brush_pose(), 1.02, -0.035, 0.040),
		_music_pose(_front_contact_pose(), 0.72, -0.020, 0.000),
	], false)


func _music_pose(base_pose: Dictionary, arm_open: float, torso_angle: float, lift_delta: float) -> Dictionary:
	var pose := base_pose.duplicate(true)
	var rig_position: Vector3 = pose["Rig:position"]
	pose["Rig:position"] = rig_position + Vector3(0.0, lift_delta, 0.0)
	pose["Rig/Pelvis/Torso:rotation"] = _rz(torso_angle)
	pose["Rig/Pelvis/Torso/Head:rotation"] = _rz(-torso_angle * 0.45)
	pose["Rig/Pelvis/Torso/ArmBackShoulder:rotation"] = _rz(-arm_open)
	pose["Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation"] = _rz(0.26)
	pose["Rig/Pelvis/Torso/ArmFrontShoulder:rotation"] = _rz(arm_open)
	pose["Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation"] = _rz(0.26)
	return pose
