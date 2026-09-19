extends Node3D

# Phase 10.2 — semantic mannequin-to-humanoid retarget.
#
# Coordinate contract:
# - Dancer/gameplay travels along +X.
# - +Y is world up.
# - The audience is on +Z.
# - The imported girl's visual front is local +Z.
# - ballerina_visual_v_1.tscn rotates that +Z front onto +X for travel.
#
# The source mannequin and the skinned humanoid do NOT share bone-local axes.
# Therefore no source X/Y/Z Euler angle is copied into a target bone. Instead:
# 1. sample each mannequin joint's accumulated orientation relative to Rig,
# 2. orient that delta by Rig's current presentation yaw,
# 3. express the delta in world space,
# 4. left-multiply the humanoid's own captured idle basis,
# 5. convert the result back to Skeleton3D space.
#
# This preserves movement direction while keeping every target bone's native
# rest basis, proportions, hierarchy and skinning intact. Dancer remains the
# sole owner of gameplay translation, collision, timing and route logic.

const RETARGET_STATES := {
	# Stage states are intercepted so imported locomotion clips cannot fight the
	# authored presentation. Only the SOURCE ROOT turn is reused; mannequin limb
	# articulation is never copied into the humanoid.
	&"STAGE_BOW": true,
	&"STAGE_READY": true,
	&"STAGE_FINAL_BOW": true,
	&"STAGE_EXIT_TURN": true,
}

const OVERLAY_STATES := {
	# Dynamic movement keeps the imported humanoid clip as its natural base.
	# These overlays only shape ballet line, contact absorption and emergency
	# balance without rebuilding the full skeleton from mannequin poses.
	&"JUMP": true,
	&"AIRBORNE": true,
	&"LANDING": true,
	&"STUMBLE": true,
	&"RECOVERY": true,
}

# Native humanoid clips own ordinary locomotion: idle/walk/run/jump/landing,
# BALANCE, LOW_TRANSITION and MUSIC_* all stay on the imported rig. This is
# deliberate: the mannequin remains choreography reference, not a frame-by-frame
# puppeteer for a skeleton with different proportions and intermediate joints.

const STAGE_BOW_DURATION := 1.65
const STAGE_BOW_TURN_TIME := 0.28
const STAGE_FINAL_BOW_DURATION := 2.60
const STAGE_FINAL_TURN_TIME := 0.32
const STUMBLE_DURATION := 0.24
const RECOVERY_DURATION := 0.62

@onready var _model_root: Node3D = $low_poly_girl
@onready var _skeleton: Skeleton3D = $low_poly_girl/Rig/Skeleton3D
@onready var _animation_player: AnimationPlayer = $low_poly_girl/AnimationPlayer

var _source_visual: Node3D
var _source_rig: Node3D
var _dancer: CharacterBody3D

var _model_base_transform: Transform3D
var _bound := false
var _retarget_active := false
var _last_state: StringName = &""
var _state_elapsed := 0.0
var _motion_scale := 1.0

var _bindings: Array[Dictionary] = []
var _binding_by_label: Dictionary = {}
var _target_idle_poses: Dictionary = {}
var _target_idle_globals: Dictionary = {}
var _target_tpose_globals: Dictionary = {}
var _tpose_available := false

var _left_hand_idx := -1
var _right_hand_idx := -1
var _left_toe_idx := -1
var _right_toe_idx := -1
var _trip_uses_left_foot := false


func _ready() -> void:
	process_priority = 100
	_model_base_transform = _model_root.transform
	call_deferred("_try_bind")


func handles_visual_state(state: StringName) -> bool:
	return RETARGET_STATES.has(state)


func _process(delta: float) -> void:
	if not _bound:
		_try_bind()
		return

	if not is_instance_valid(_source_visual) or not is_instance_valid(_source_rig):
		_bound = false
		_retarget_active = false
		return

	var state := &""
	if _source_visual.has_method("get_visual_state"):
		state = StringName(_source_visual.call("get_visual_state"))

	if state != _last_state:
		_last_state = state
		_state_elapsed = 0.0
		if state == &"STUMBLE":
			_capture_trip_side_from_current_run()
	else:
		_state_elapsed += delta

	if RETARGET_STATES.has(state):
		if not _retarget_active:
			_animation_player.stop()
			_retarget_active = true

		_apply_idle_baseline()
		_apply_source_root_transform()
		_apply_stage_presentation_calibration(state)
		return

	# Locomotion is evaluated by the imported AnimationPlayer. This script runs
	# later in the frame (process_priority = 100), so stumble/recovery can steer
	# selected chains on top of the natural run cycle without erasing its spine,
	# clavicle, wrist, toe and secondary-body motion.
	if _retarget_active:
		_model_root.transform = _model_base_transform
		_retarget_active = false

	_sync_native_run_speed(state)

	if OVERLAY_STATES.has(state):
		_model_root.transform = _model_base_transform
		if state == &"JUMP" or state == &"AIRBORNE" or state == &"LANDING":
			_apply_air_motion_overlay(state)
		else:
			_apply_running_trip_overlay(state)


func _sync_native_run_speed(state: StringName) -> void:
	if state in [&"JUMP", &"AIRBORNE", &"LANDING"]:
		return
	if _animation_player.current_animation != "run":
		return

	var backward_speed := float(
		_animation_player.get_meta("_gait_backward_speed_run", 0.0)
	)
	if backward_speed <= 0.05:
		return

	var desired_speed := absf(_dancer.velocity.x)
	if desired_speed <= 0.05:
		return

	# Keep the support-foot backward speed matched to CharacterBody translation
	# every frame. This is what removes the residual scrape as STUMBLE/RECOVERY
	# change world velocity continuously.
	_animation_player.speed_scale = clampf(
		desired_speed / backward_speed,
		0.62,
		1.55
	)


func _try_bind() -> void:
	if _bound:
		return

	_dancer = get_parent() as CharacterBody3D
	if _dancer == null:
		return

	_source_visual = _dancer.get_node_or_null("DancerVisual") as Node3D
	if _source_visual == null or _skeleton == null or _animation_player == null:
		return

	_source_rig = _source_visual.get_node_or_null("Rig") as Node3D
	if _source_rig == null:
		return

	_bindings = _resolve_bindings()
	if _bindings.is_empty():
		push_warning("Ballerina retarget v2 could not resolve humanoid bindings.")
		return

	for binding in _bindings:
		_binding_by_label[String(binding["label"])] = binding

	_capture_idle_baseline()
	_capture_tpose_baseline()
	_resolve_optional_hands()
	_motion_scale = _compute_motion_scale()
	_bound = true

	print(
		"Ballerina retarget v2 ready: %d semantic joints, motion scale %.3f."
		% [_bindings.size(), _motion_scale]
	)


func _resolve_bindings() -> Array[Dictionary]:
	var specs := [
		{
			"label": "Pelvis",
			"source": NodePath("Rig/Pelvis"),
			"aliases": ["hips", "pelvis"],
		},
		{
			"label": "Torso",
			"source": NodePath("Rig/Pelvis/Torso"),
			"aliases": ["chest", "upperchest", "spine2", "spine02", "spine1", "spine01", "spine"],
		},
		{
			"label": "Head",
			"source": NodePath("Rig/Pelvis/Torso/Head"),
			"aliases": ["head"],
		},
		{
			"label": "ArmBackShoulder",
			"source": NodePath("Rig/Pelvis/Torso/ArmBackShoulder"),
			"aliases": ["leftupperarm", "upperarml", "leftarm", "arml"],
		},
		{
			"label": "ArmBackElbow",
			"source": NodePath("Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow"),
			"aliases": ["leftlowerarm", "lowerarml", "leftforearm", "forearml"],
		},
		{
			"label": "ArmFrontShoulder",
			"source": NodePath("Rig/Pelvis/Torso/ArmFrontShoulder"),
			"aliases": ["rightupperarm", "upperarmr", "rightarm", "armr"],
		},
		{
			"label": "ArmFrontElbow",
			"source": NodePath("Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow"),
			"aliases": ["rightlowerarm", "lowerarmr", "rightforearm", "forearmr"],
		},
		{
			"label": "LegBackHip",
			"source": NodePath("Rig/Pelvis/LegBackHip"),
			"aliases": ["leftupperleg", "upperlegl", "leftupleg", "leftthigh", "thighl"],
		},
		{
			"label": "LegBackKnee",
			"source": NodePath("Rig/Pelvis/LegBackHip/LegBackKnee"),
			"aliases": ["leftlowerleg", "lowerlegl", "leftleg", "leftcalf", "calfl", "leftshin", "shinl"],
		},
		{
			"label": "FootBack",
			"source": NodePath("Rig/Pelvis/LegBackHip/LegBackKnee/FootBack"),
			"aliases": ["leftfoot", "footl"],
		},
		{
			"label": "LegFrontHip",
			"source": NodePath("Rig/Pelvis/LegFrontHip"),
			"aliases": ["rightupperleg", "upperlegr", "rightupleg", "rightthigh", "thighr"],
		},
		{
			"label": "LegFrontKnee",
			"source": NodePath("Rig/Pelvis/LegFrontHip/LegFrontKnee"),
			"aliases": ["rightlowerleg", "lowerlegr", "rightleg", "rightcalf", "calfr", "rightshin", "shinr"],
		},
		{
			"label": "FootFront",
			"source": NodePath("Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront"),
			"aliases": ["rightfoot", "footr"],
		},
	]

	var resolved: Array[Dictionary] = []
	for spec in specs:
		var source_node := _source_visual.get_node_or_null(spec["source"]) as Node3D
		if source_node == null:
			push_warning("Ballerina retarget missing source joint: %s" % String(spec["label"]))
			continue

		var bone_idx := _find_bone(spec["aliases"])
		if bone_idx < 0:
			push_warning("Ballerina retarget unresolved target bone: %s" % String(spec["label"]))
			continue

		resolved.append({
			"label": String(spec["label"]),
			"source_node": source_node,
			"bone_idx": bone_idx,
		})
		print(
			"Ballerina retarget map: %s -> %s"
			% [String(spec["label"]), String(_skeleton.get_bone_name(bone_idx))]
		)

	return resolved


func _find_bone(aliases: Array) -> int:
	var normalized_aliases: Array[String] = []
	for alias in aliases:
		normalized_aliases.append(_normalize_name(String(alias)))

	for bone_idx in range(_skeleton.get_bone_count()):
		var normalized_name := _normalize_name(_skeleton.get_bone_name(bone_idx))
		if normalized_name in normalized_aliases:
			return bone_idx

	for bone_idx in range(_skeleton.get_bone_count()):
		var normalized_name := _normalize_name(_skeleton.get_bone_name(bone_idx))
		for alias in normalized_aliases:
			if normalized_name.ends_with(alias) or alias.ends_with(normalized_name):
				return bone_idx

	return -1


func _normalize_name(value: String) -> String:
	return (
		value.to_lower()
		.replace("mixamorig", "")
		.replace(":", "")
		.replace("_", "")
		.replace(".", "")
		.replace("-", "")
		.replace(" ", "")
	)


func _capture_idle_baseline() -> void:
	var previous_animation := _animation_player.current_animation
	var previous_position := _animation_player.current_animation_position
	var was_playing := _animation_player.is_playing()

	if _animation_player.has_animation("idle"):
		_animation_player.play("idle")
		_animation_player.seek(0.0, true)
		_animation_player.advance(0.0)

	for bone_idx in range(_skeleton.get_bone_count()):
		_target_idle_poses[bone_idx] = _skeleton.get_bone_pose(bone_idx)
		_target_idle_globals[bone_idx] = _skeleton.get_bone_global_pose(bone_idx)

	_restore_animation_player(previous_animation, previous_position, was_playing)


func _capture_tpose_baseline() -> void:
	var tpose_name := _find_tpose_animation()
	if tpose_name == &"":
		return

	var previous_animation := _animation_player.current_animation
	var previous_position := _animation_player.current_animation_position
	var was_playing := _animation_player.is_playing()

	_animation_player.play(tpose_name)
	_animation_player.seek(0.0, true)
	_animation_player.advance(0.0)

	for bone_idx in range(_skeleton.get_bone_count()):
		_target_tpose_globals[bone_idx] = _skeleton.get_bone_global_pose(bone_idx)

	_tpose_available = true
	_restore_animation_player(previous_animation, previous_position, was_playing)


func _find_tpose_animation() -> StringName:
	for candidate in [&"_T-Pose", &"T-Pose", &"_T_Pose", &"TPose"]:
		if _animation_player.has_animation(candidate):
			return candidate
	return &""


func _restore_animation_player(
	previous_animation: StringName,
	previous_position: float,
	was_playing: bool
) -> void:
	if previous_animation != &"" and _animation_player.has_animation(previous_animation):
		_animation_player.play(previous_animation)
		_animation_player.seek(previous_position, true)
		if not was_playing:
			_animation_player.pause()
	else:
		_animation_player.stop()


func _resolve_optional_hands() -> void:
	_left_hand_idx = _find_bone(["lefthand", "handl"])
	_right_hand_idx = _find_bone(["righthand", "handr"])
	_left_toe_idx = _find_bone(["lefttoebase", "lefttoe", "toel", "balll"])
	_right_toe_idx = _find_bone(["righttoebase", "righttoe", "toer", "ballr"])


func _compute_motion_scale() -> float:
	var pelvis_binding := _binding("Pelvis")
	var torso_binding := _binding("Torso")
	var head_binding := _binding("Head")
	if pelvis_binding.is_empty() or torso_binding.is_empty() or head_binding.is_empty():
		return 1.0

	var source_torso: Node3D = torso_binding["source_node"]
	var source_head: Node3D = head_binding["source_node"]
	var source_span := source_torso.position.length() + source_head.position.length()
	if source_span <= 0.0001:
		return 1.0

	var pelvis_idx: int = pelvis_binding["bone_idx"]
	var torso_idx: int = torso_binding["bone_idx"]
	var head_idx: int = head_binding["bone_idx"]
	var pelvis_global: Transform3D = _target_idle_globals[pelvis_idx]
	var torso_global: Transform3D = _target_idle_globals[torso_idx]
	var head_global: Transform3D = _target_idle_globals[head_idx]
	var target_span := (
		(torso_global.origin - pelvis_global.origin).length()
		+ (head_global.origin - torso_global.origin).length()
	)
	if target_span <= 0.0001:
		return 1.0

	return clampf(target_span / source_span, 0.60, 1.80)


func _apply_idle_baseline() -> void:
	for bone_idx in range(_skeleton.get_bone_count()):
		if _target_idle_poses.has(bone_idx):
			_skeleton.set_bone_pose(bone_idx, _target_idle_poses[bone_idx])


func _apply_source_root_transform() -> void:
	# Rig.position is authored in DancerVisual/Dancer coordinates, so the same
	# vector belongs directly in BallerinaVisual/Dancer coordinates. Rig's local
	# Y rotation is the presentation turn: identity while travelling, -90° when
	# the source faces the audience. Multiplying it after the accepted GLB base
	# transform preserves the already-verified run direction and reproduces the
	# exact 90° stage turn without camera guesses or duplicated yaw.
	var source_root_basis := _source_rig.transform.basis.orthonormalized()
	var source_offset := _source_rig.position * _motion_scale
	_model_root.transform = Transform3D(
		(_model_base_transform.basis * source_root_basis).orthonormalized(),
		_model_base_transform.origin + source_offset
	)


func _apply_semantic_motion_retarget(state: StringName) -> void:
	var rig_frame := _source_rig.transform.basis.orthonormalized()
	var rig_frame_inverse := rig_frame.inverse()

	var source_rig_world := _source_rig.global_transform.basis.orthonormalized()
	var source_rig_world_inverse := source_rig_world.inverse()

	# DancerVisual's basis is the shared gameplay frame (+X travel, +Y up, +Z
	# audience). This frame is stable even when the mannequin Rig turns for a
	# stage presentation.
	var common_world := _source_visual.global_transform.basis.orthonormalized()
	var common_world_inverse := common_world.inverse()

	var skeleton_world := _skeleton.global_transform.basis.orthonormalized()
	var skeleton_world_inverse := skeleton_world.inverse()

	for binding in _bindings:
		var source_node: Node3D = binding["source_node"]
		var bone_idx: int = binding["bone_idx"]
		var label := String(binding["label"])
		if not is_instance_valid(source_node):
			continue
		if not _target_idle_globals.has(bone_idx):
			continue

		# Opening révérence is authored directly on the humanoid. The source Rig
		# still supplies the verified +X -> +Z stage turn, but no mannequin limb
		# articulation is transferred during BOW/READY. This avoids reverse-knee
		# silhouettes and lets both knees track anatomically toward the audience.
		if state == &"STAGE_BOW" or state == &"STAGE_READY":
			continue

		# The mannequin's joints have identity rest bases. Removing Rig's current
		# world basis therefore gives the complete articulated pose in Rig space.
		var source_pose_in_rig := (
			source_rig_world_inverse
			* source_node.global_transform.basis.orthonormalized()
		).orthonormalized()

		# Do not apply Rig yaw as an extra bone rotation. Conjugate the articulated
		# delta by that yaw so its AXIS follows the dancer's current facing instead.
		# Example: a side-view Z-axis torso hinge becomes the correct sagittal hinge
		# after the dancer turns 90° to the audience.
		var oriented_delta_in_gameplay := (
			rig_frame
			* source_pose_in_rig
			* rig_frame_inverse
		).orthonormalized()

		var delta_world := (
			common_world
			* oriented_delta_in_gameplay
			* common_world_inverse
		).orthonormalized()

		var baseline_global: Transform3D = _target_idle_globals[bone_idx]
		var baseline_world_basis := (
			skeleton_world * baseline_global.basis
		).orthonormalized()
		var desired_world_basis := (
			delta_world * baseline_world_basis
		).orthonormalized()
		var desired_skeleton_basis := (
			skeleton_world_inverse * desired_world_basis
		).orthonormalized()

		# Position/length comes from the humanoid skeleton. Only orientation is
		# transferred, so no mannequin proportion or joint offset can deform it.
		var current_global := _skeleton.get_bone_global_pose(bone_idx)
		_skeleton.set_bone_global_pose(
			bone_idx,
			Transform3D(desired_skeleton_basis, current_global.origin)
		)


func _apply_air_motion_overlay(state: StringName) -> void:
	# Preserve the imported jump/fall/landing clips as the motion base. These
	# small overlays only refine line, head carriage and port de bras; legs remain
	# native during flight/contact so the body keeps believable weight.
	if state == &"JUMP":
		var t := clampf(_state_elapsed / 0.16, 0.0, 1.0)
		var strength := 0.30 * smoothstep(0.0, 0.70, t)
		_steer_current_chain_world_direction(
			"Pelvis",
			"Torso",
			Vector3(0.10, 0.995, 0.0).normalized(),
			strength
		)
		_steer_current_chain_world_direction(
			"Torso",
			"Head",
			Vector3(0.02, 0.999, 0.0).normalized(),
			strength
		)
		_apply_air_port_de_bras(
			Vector3(-0.82, 0.26, 0.18),
			Vector3(0.84, 0.34, 0.16),
			strength
		)
		_apply_air_toe_line(0.24 * strength / 0.30)
		return

	if state == &"AIRBORNE":
		var descent := clampf(maxf(-_dancer.velocity.y, 0.0) / 7.0, 0.0, 1.0)
		var strength := 0.30
		var back_arm := Vector3(-0.86, 0.18, 0.22).lerp(
			Vector3(-0.72, -0.10, 0.34),
			descent
		).normalized()
		var front_arm := Vector3(0.88, 0.28, 0.18).lerp(
			Vector3(0.74, -0.06, 0.32),
			descent
		).normalized()
		_steer_current_chain_world_direction(
			"Pelvis",
			"Torso",
			Vector3(0.08, 0.997, 0.0).normalized(),
			strength
		)
		_steer_current_chain_world_direction(
			"Torso",
			"Head",
			Vector3(0.01, 1.0, 0.0).normalized(),
			strength
		)
		_apply_air_port_de_bras(back_arm, front_arm, strength)
		_apply_air_toe_line(0.28)
		return

	if state != &"LANDING":
		return

	var t := clampf(_state_elapsed / 0.22, 0.0, 1.0)
	var drop_distance := 0.0
	var was_jump := false
	if _dancer.has_method("get_last_landing_drop_distance"):
		drop_distance = float(_dancer.call("get_last_landing_drop_distance"))
	if _dancer.has_method("get_last_landing_was_jump"):
		was_jump = bool(_dancer.call("get_last_landing_was_jump"))

	# Compression peaks after contact and is fully released before the next run
	# step. High drops absorb more deeply; an ordinary jump stays lighter.
	var impact := 0.58 if was_jump else clampf(
		0.58 + drop_distance * 0.24,
		0.58,
		0.96
	)
	var compression_curve := sin(PI * clampf(t / 0.92, 0.0, 1.0))
	var leg_strength := 0.48 * impact * compression_curve
	var upper_strength := 0.30 * impact * compression_curve

	var support_left := bool(
		_animation_player.get_meta("_landing_support_left", false)
	)
	var support_hip := "LegBackHip" if support_left else "LegFrontHip"
	var support_knee := "LegBackKnee" if support_left else "LegFrontKnee"
	var side := -0.04 if support_left else 0.04

	# The landing foot stays planted while the knee travels forward along +X and
	# the shin folds back toward the foot. This is the running equivalent of a
	# ballet plié: absorb through ankle/knee/hip, never bounce vertically from
	# the same support foot.
	_steer_current_chain_world_direction(
		support_hip,
		support_knee,
		Vector3(0.26, -0.964, side).normalized(),
		leg_strength
	)
	_steer_current_chain_world_direction(
		support_knee,
		"FootBack" if support_left else "FootFront",
		Vector3(-0.18, -0.983, side * 0.45).normalized(),
		leg_strength
	)

	# Long torso yields slightly forward over the planted leg. Arms open low and
	# rounded for balance, then release before the opposite-foot run contact.
	_steer_current_chain_world_direction(
		"Pelvis",
		"Torso",
		Vector3(0.14 + 0.05 * impact, 0.985, 0.0).normalized(),
		upper_strength
	)
	_steer_current_chain_world_direction(
		"Torso",
		"Head",
		Vector3(0.02, 0.999, 0.0).normalized(),
		upper_strength * 0.78
	)
	_apply_air_port_de_bras(
		Vector3(-0.70, -0.30, 0.28),
		Vector3(0.72, -0.27, 0.26),
		upper_strength
	)


func _apply_air_port_de_bras(
	back_upper_direction: Vector3,
	front_upper_direction: Vector3,
	strength: float
) -> void:
	_steer_current_chain_world_direction(
		"ArmBackShoulder",
		"ArmBackElbow",
		back_upper_direction.normalized(),
		strength
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmBackElbow"),
		_left_hand_idx,
		(back_upper_direction + Vector3(-0.10, -0.18, 0.18)).normalized(),
		strength * 0.86
	)
	_steer_current_chain_world_direction(
		"ArmFrontShoulder",
		"ArmFrontElbow",
		front_upper_direction.normalized(),
		strength
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmFrontElbow"),
		_right_hand_idx,
		(front_upper_direction + Vector3(0.10, -0.18, 0.18)).normalized(),
		strength * 0.86
	)


func _apply_air_toe_line(strength: float) -> void:
	var weight := clampf(strength, 0.0, 0.30)
	_steer_current_segment_world_direction(
		_binding_index("FootBack"),
		_left_toe_idx,
		Vector3(-0.08, -0.995, 0.02).normalized(),
		weight
	)
	_steer_current_segment_world_direction(
		_binding_index("FootFront"),
		_right_toe_idx,
		Vector3(0.10, -0.994, 0.02).normalized(),
		weight
	)


func _capture_trip_side_from_current_run() -> void:
	var left_foot_idx := _binding_index("FootBack")
	var right_foot_idx := _binding_index("FootFront")
	if left_foot_idx < 0 or right_foot_idx < 0:
		_trip_uses_left_foot = false
		return

	var skeleton_world := _skeleton.global_transform
	var left_pose := _skeleton.get_bone_global_pose(left_foot_idx)
	var right_pose := _skeleton.get_bone_global_pose(right_foot_idx)
	var left_world := skeleton_world * left_pose.origin
	var right_world := skeleton_world * right_pose.origin

	# Gameplay advances along +X, so the foot farther forward at obstacle contact
	# is the foot most plausibly caught. This keeps trip/recovery synchronized
	# with the native run gait instead of always forcing the same leg.
	_trip_uses_left_foot = left_world.x > right_world.x


func _apply_running_trip_overlay(state: StringName) -> void:
	if state == &"STUMBLE":
		var t := clampf(_state_elapsed / STUMBLE_DURATION, 0.0, 1.0)
		var impact := smoothstep(0.0, 1.0, t)
		var torso_strength := 0.42 * smoothstep(0.04, 0.68, t)
		var trip_leg_strength := 0.50 * smoothstep(0.0, 0.50, t)
		var arm_strength := 0.34 * smoothstep(0.18, 0.82, t)

		# Keep the CoM moving forward. Only a slight visual lag is needed to read
		# the caught toe; vertical motion remains owned by CharacterBody3D.
		_model_root.position += Vector3(
			-0.050 * impact,
			0.0,
			0.0
		)

		# Toe catch -> forward pitch. Head counter-extends so the gaze does not
		# collapse with the chest.
		_steer_current_chain_world_direction(
			"Pelvis",
			"Torso",
			Vector3(0.48, 0.87, -0.05).lerp(
				Vector3(0.08, 0.997, 0.0),
				1.0 - impact
			).normalized(),
			torso_strength
		)
		_steer_current_chain_world_direction(
			"Torso",
			"Head",
			Vector3(0.12, 0.992, 0.0).normalized(),
			torso_strength * 0.80
		)

		# Constrain whichever foot is actually leading into the obstacle. The
		# opposite leg stays on the native run clip and remains free to save the
		# fall with a reflex catch step.
		var trip_hip := "LegBackHip" if _trip_uses_left_foot else "LegFrontHip"
		var trip_knee := "LegBackKnee" if _trip_uses_left_foot else "LegFrontKnee"
		var trip_foot := "FootBack" if _trip_uses_left_foot else "FootFront"
		var trip_toe := _left_toe_idx if _trip_uses_left_foot else _right_toe_idx
		var trip_side := 0.03 if _trip_uses_left_foot else -0.03
		_steer_current_chain_world_direction(
			trip_hip,
			trip_knee,
			Vector3(0.26, -0.965, trip_side).normalized(),
			trip_leg_strength
		)
		_steer_current_chain_world_direction(
			trip_knee,
			trip_foot,
			Vector3(0.07, -0.997, trip_side * 0.30).normalized(),
			trip_leg_strength
		)
		_steer_current_segment_world_direction(
			_binding_index(trip_foot),
			trip_toe,
			Vector3(0.95, 0.30, trip_side).normalized(),
			trip_leg_strength * 0.82
		)

		# Human bracing is delayed and asymmetric, not an instant mirrored flail.
		_steer_current_chain_world_direction(
			"ArmFrontShoulder",
			"ArmFrontElbow",
			Vector3(0.78, -0.42, -0.18).normalized(),
			arm_strength
		)
		_steer_current_segment_world_direction(
			_binding_index("ArmFrontElbow"),
			_right_hand_idx,
			Vector3(0.50, -0.78, -0.20).normalized(),
			arm_strength * 0.82
		)
		_steer_current_chain_world_direction(
			"ArmBackShoulder",
			"ArmBackElbow",
			Vector3(0.56, -0.54, 0.40).normalized(),
			arm_strength
		)
		_steer_current_segment_world_direction(
			_binding_index("ArmBackElbow"),
			_left_hand_idx,
			Vector3(0.26, -0.86, 0.36).normalized(),
			arm_strength * 0.82
		)
		return

	if state != &"RECOVERY":
		return

	var t := clampf(_state_elapsed / RECOVERY_DURATION, 0.0, 1.0)
	var release := smoothstep(0.0, 1.0, t)
	var torso_strength := 0.36 * (1.0 - smoothstep(0.35, 0.90, t))
	var catch_step_strength := 0.44 * sin(
		PI * clampf(t / 0.86, 0.0, 1.0)
	)
	var arm_strength := 0.28 * (1.0 - smoothstep(0.46, 0.92, t))

	_model_root.position += Vector3(
		-0.050 * (1.0 - release),
		0.0,
		0.0
	)

	# Torso returns over the support base continuously; there is no recovery
	# "snap" back to vertical.
	_steer_current_chain_world_direction(
		"Pelvis",
		"Torso",
		Vector3(0.42, 0.90, -0.04).lerp(
			Vector3(0.05, 0.999, 0.0),
			release
		).normalized(),
		torso_strength
	)
	_steer_current_chain_world_direction(
		"Torso",
		"Head",
		Vector3(0.08, 0.996, 0.0).normalized(),
		torso_strength * 0.72
	)

	# The leg opposite the caught foot makes one emergency forward catch step.
	# The overlay peaks mid-recovery then disappears into the native run.
	var catch_hip := "LegFrontHip" if _trip_uses_left_foot else "LegBackHip"
	var catch_knee := "LegFrontKnee" if _trip_uses_left_foot else "LegBackKnee"
	var caught_foot := "FootBack" if _trip_uses_left_foot else "FootFront"
	var caught_toe := _left_toe_idx if _trip_uses_left_foot else _right_toe_idx
	var catch_side := -0.04 if _trip_uses_left_foot else 0.04
	_steer_current_chain_world_direction(
		catch_hip,
		catch_knee,
		Vector3(0.42, -0.90, catch_side).normalized(),
		catch_step_strength
	)
	_steer_current_chain_world_direction(
		catch_knee,
		"FootFront" if _trip_uses_left_foot else "FootBack",
		Vector3(0.24, -0.97, catch_side * 0.50).normalized(),
		catch_step_strength
	)
	_steer_current_segment_world_direction(
		_binding_index(caught_foot),
		caught_toe,
		Vector3(0.20, -0.98, -catch_side * 0.30).normalized(),
		0.24 * (1.0 - release)
	)

	_steer_current_chain_world_direction(
		"ArmFrontShoulder",
		"ArmFrontElbow",
		Vector3(0.56, -0.70, -0.18).normalized(),
		arm_strength
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmFrontElbow"),
		_right_hand_idx,
		Vector3(0.32, -0.90, -0.16).normalized(),
		arm_strength * 0.80
	)
	_steer_current_chain_world_direction(
		"ArmBackShoulder",
		"ArmBackElbow",
		Vector3(-0.10, -0.80, 0.52).normalized(),
		arm_strength
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmBackElbow"),
		_left_hand_idx,
		Vector3(0.04, -0.94, 0.32).normalized(),
		arm_strength * 0.80
	)


func _steer_current_chain_world_direction(
	parent_label: String,
	child_label: String,
	desired_world_direction: Vector3,
	strength: float
) -> void:
	var parent_idx := _binding_index(parent_label)
	var child_idx := _binding_index(child_label)
	_steer_current_segment_world_direction(
		parent_idx,
		child_idx,
		desired_world_direction,
		strength
	)


func _steer_current_segment_world_direction(
	parent_idx: int,
	child_idx: int,
	desired_world_direction: Vector3,
	strength: float
) -> void:
	if parent_idx < 0 or child_idx < 0:
		return
	if desired_world_direction.length_squared() <= 0.000001:
		return

	var parent_current := _skeleton.get_bone_global_pose(parent_idx)
	var child_current := _skeleton.get_bone_global_pose(child_idx)
	var segment_in_skeleton := child_current.origin - parent_current.origin
	if segment_in_skeleton.length_squared() <= 0.000001:
		return

	var skeleton_world := _skeleton.global_transform.basis.orthonormalized()
	var skeleton_world_inverse := skeleton_world.inverse()
	var current_direction_world := (
		skeleton_world * segment_in_skeleton.normalized()
	).normalized()
	var desired := desired_world_direction.normalized()

	if current_direction_world.dot(desired) < -0.9999:
		desired = (desired + Vector3(0.0, 0.0001, 0.0001)).normalized()

	# Rotate the pose the stock clip already produced. This is the critical
	# difference from v2: we do not rebuild the limb from idle/rest, so the
	# imported animation keeps its natural twist, elbow/knee bend and follow-
	# through. We only redirect the chain toward the physically required vector.
	var align_world := Basis(Quaternion(current_direction_world, desired))
	var current_world_basis := (
		skeleton_world * parent_current.basis
	).orthonormalized()
	var steered_world_basis := (
		align_world * current_world_basis
	).orthonormalized()
	var steered_skeleton_basis := (
		skeleton_world_inverse * steered_world_basis
	).orthonormalized()

	var weight := clampf(strength, 0.0, 1.0)
	var blended_quat := parent_current.basis.get_rotation_quaternion().slerp(
		steered_skeleton_basis.get_rotation_quaternion(),
		weight
	)
	_skeleton.set_bone_global_pose(
		parent_idx,
		Transform3D(Basis(blended_quat), parent_current.origin)
	)


func _binding_index(label: String) -> int:
	var binding := _binding(label)
	if binding.is_empty():
		return -1
	return int(binding["bone_idx"])


func _apply_stage_presentation_calibration(state: StringName) -> void:
	match state:
		&"STAGE_BOW":
			# Turn fully toward the +Z audience first; then perform a compact
			# classical révérence. No limb pose is inherited from the mannequin.
			var phase := clampf(
				(_state_elapsed - STAGE_BOW_TURN_TIME)
				/ maxf(STAGE_BOW_DURATION - STAGE_BOW_TURN_TIME, 0.001),
				0.0,
				1.0
			)
			_apply_classical_reverence_upper_body(phase, false)
		&"STAGE_READY":
			_apply_classical_reverence_upper_body(1.0, false)
		&"STAGE_FINAL_BOW":
			# The closing révérence uses the same anatomical rules as the
			# opening but with a deeper plié, broader port de bras and slightly
			# larger head/torso acknowledgement.
			var phase := clampf(
				(_state_elapsed - STAGE_FINAL_TURN_TIME)
				/ maxf(STAGE_FINAL_BOW_DURATION - STAGE_FINAL_TURN_TIME, 0.001),
				0.0,
				1.0
			)
			_apply_classical_reverence_upper_body(phase, true)
		&"STAGE_EXIT_TURN":
			# Idle baseline + source-root yaw gives a clean side turn before the
			# native calibrated walk resumes.
			pass


func _apply_classical_reverence_upper_body(
	phase: float,
	final_reverence: bool
) -> void:
	var p := smoothstep(0.0, 1.0, clampf(phase, 0.0, 1.0))
	var depth := sin(p * PI)
	var knee_max := 0.70 if final_reverence else 0.48
	var knee_angle := knee_max * depth
	var c := cos(knee_angle)
	var s := sin(knee_angle)

	# FRONT-FACING PLIÉ, audience = +Z.
	# Femurs travel forward toward +Z; shins fold back toward the planted feet.
	# The two sides are exact mirrors in X so no arm/leg can appear "reversed".
	var turnout := (0.13 if final_reverence else 0.095) * depth
	_steer_current_chain_world_direction(
		"LegBackHip",
		"LegBackKnee",
		Vector3(-turnout, -c, s).normalized(),
		1.0
	)
	_steer_current_chain_world_direction(
		"LegBackKnee",
		"FootBack",
		Vector3(-turnout * 0.40, -c, -s).normalized(),
		1.0
	)
	_steer_current_chain_world_direction(
		"LegFrontHip",
		"LegFrontKnee",
		Vector3(turnout, -c, s).normalized(),
		1.0
	)
	_steer_current_chain_world_direction(
		"LegFrontKnee",
		"FootFront",
		Vector3(turnout * 0.40, -c, -s).normalized(),
		1.0
	)

	var leg_shortening := _opening_leg_vertical_shortening(knee_angle)
	var max_drop := 0.18 if final_reverence else 0.12
	_model_root.position.y = (
		_model_base_transform.origin.y
		- minf(leg_shortening, max_drop)
	)

	# Rounded port de bras. Start/end in a quiet bras-bas shape and open through
	# second position at the deepest plié. Both sides are mirrored exactly.
	var arm_open := depth
	var upper_x := lerpf(0.54, 0.91 if final_reverence else 0.84, arm_open)
	var upper_y := lerpf(-0.72, -0.20 if final_reverence else -0.27, arm_open)
	var upper_z := lerpf(0.31, 0.31, arm_open)
	var fore_x := lerpf(0.30, 0.72 if final_reverence else 0.62, arm_open)
	var fore_y := lerpf(-0.88, -0.34 if final_reverence else -0.42, arm_open)
	var fore_z := lerpf(0.34, 0.60 if final_reverence else 0.54, arm_open)

	_steer_current_chain_world_direction(
		"ArmBackShoulder",
		"ArmBackElbow",
		Vector3(-upper_x, upper_y, upper_z).normalized(),
		1.0
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmBackElbow"),
		_left_hand_idx,
		Vector3(-fore_x, fore_y, fore_z).normalized(),
		1.0
	)
	_steer_current_chain_world_direction(
		"ArmFrontShoulder",
		"ArmFrontElbow",
		Vector3(upper_x, upper_y, upper_z).normalized(),
		1.0
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmFrontElbow"),
		_right_hand_idx,
		Vector3(fore_x, fore_y, fore_z).normalized(),
		1.0
	)

	# Classical épaulement stays restrained here: long spine, small acknowledgement
	# toward +Z, no waist collapse. Final révérence is larger but still upright.
	var torso_z := (0.075 if final_reverence else 0.035) * depth
	var head_z := (0.135 if final_reverence else 0.070) * depth
	_steer_current_chain_world_direction(
		"Pelvis",
		"Torso",
		Vector3(0.0, 0.997, torso_z).normalized(),
		0.82
	)
	_steer_current_chain_world_direction(
		"Torso",
		"Head",
		Vector3(0.0, 0.994, head_z).normalized(),
		0.76
	)

	# Keep feet long and turnout-aware without rising onto pointe during plié.
	_steer_current_segment_world_direction(
		_binding_index("FootBack"),
		_left_toe_idx,
		Vector3(-0.18, -0.03, 0.98).normalized(),
		0.62 * depth
	)
	_steer_current_segment_world_direction(
		_binding_index("FootFront"),
		_right_toe_idx,
		Vector3(0.18, -0.03, 0.98).normalized(),
		0.62 * depth
	)


func _opening_leg_vertical_shortening(angle: float) -> float:
	if angle <= 0.0001:
		return 0.0

	var totals: Array[float] = []
	for labels in [
		["LegBackHip", "LegBackKnee", "FootBack"],
		["LegFrontHip", "LegFrontKnee", "FootFront"],
	]:
		var hip_idx := _binding_index(labels[0])
		var knee_idx := _binding_index(labels[1])
		var foot_idx := _binding_index(labels[2])
		if (
			hip_idx < 0
			or knee_idx < 0
			or foot_idx < 0
			or not _target_idle_globals.has(hip_idx)
			or not _target_idle_globals.has(knee_idx)
			or not _target_idle_globals.has(foot_idx)
		):
			continue

		var hip: Transform3D = _target_idle_globals[hip_idx]
		var knee: Transform3D = _target_idle_globals[knee_idx]
		var foot: Transform3D = _target_idle_globals[foot_idx]
		totals.append(
			(knee.origin - hip.origin).length()
			+ (foot.origin - knee.origin).length()
		)

	var leg_length := 0.90
	if not totals.is_empty():
		leg_length = 0.0
		for total in totals:
			leg_length += total
		leg_length /= float(totals.size())

	return clampf(
		leg_length * (1.0 - cos(angle)),
		0.0,
		0.14
	)


func _apply_accepted_reverence_arm(label: String, z_angle: float) -> void:
	var binding := _binding(label)
	if binding.is_empty():
		return
	var bone_idx: int = binding["bone_idx"]

	var baseline: Transform3D
	if _target_tpose_globals.has(bone_idx):
		baseline = _target_tpose_globals[bone_idx]
	elif _target_idle_globals.has(bone_idx):
		baseline = _target_idle_globals[bone_idx]
	else:
		return

	var desired_basis := (
		Basis(Vector3(0.0, 0.0, 1.0), z_angle)
		* baseline.basis
	).orthonormalized()
	var current := _skeleton.get_bone_global_pose(bone_idx)
	_skeleton.set_bone_global_pose(
		bone_idx,
		Transform3D(desired_basis, current.origin)
	)


func _apply_accepted_reverence_body(label: String, x_angle: float) -> void:
	var binding := _binding(label)
	if binding.is_empty():
		return
	var bone_idx: int = binding["bone_idx"]
	if not _target_idle_globals.has(bone_idx):
		return

	var baseline: Transform3D = _target_idle_globals[bone_idx]
	var desired_basis := (
		Basis(Vector3.RIGHT, x_angle)
		* baseline.basis
	).orthonormalized()
	var current := _skeleton.get_bone_global_pose(bone_idx)
	_skeleton.set_bone_global_pose(
		bone_idx,
		Transform3D(desired_basis, current.origin)
	)


func _apply_lowered_tpose_chain(
	shoulder_label: String,
	elbow_label: String,
	hand_idx: int,
	shoulder_drop: float,
	elbow_drop: float
) -> void:
	var shoulder_binding := _binding(shoulder_label)
	var elbow_binding := _binding(elbow_label)
	if shoulder_binding.is_empty() or elbow_binding.is_empty():
		return

	var shoulder_idx: int = shoulder_binding["bone_idx"]
	var elbow_idx: int = elbow_binding["bone_idx"]
	if not _target_tpose_globals.has(shoulder_idx) or not _target_tpose_globals.has(elbow_idx):
		return

	var shoulder_base: Transform3D = _target_tpose_globals[shoulder_idx]
	var elbow_base: Transform3D = _target_tpose_globals[elbow_idx]
	var upper_direction := (elbow_base.origin - shoulder_base.origin).normalized()
	var upper_rotation := _downward_rotation_about_visual_front(upper_direction, shoulder_drop)

	var shoulder_current := _skeleton.get_bone_global_pose(shoulder_idx)
	_skeleton.set_bone_global_pose(
		shoulder_idx,
		Transform3D(
			(upper_rotation * shoulder_base.basis).orthonormalized(),
			shoulder_current.origin
		)
	)

	if hand_idx < 0 or not _target_tpose_globals.has(hand_idx):
		return

	var hand_base: Transform3D = _target_tpose_globals[hand_idx]
	var forearm_direction := (hand_base.origin - elbow_base.origin).normalized()
	var forearm_rotation := _downward_rotation_about_visual_front(forearm_direction, elbow_drop)
	var elbow_current := _skeleton.get_bone_global_pose(elbow_idx)
	_skeleton.set_bone_global_pose(
		elbow_idx,
		Transform3D(
			(forearm_rotation * elbow_base.basis).orthonormalized(),
			elbow_current.origin
		)
	)


func _downward_rotation_about_visual_front(direction: Vector3, magnitude: float) -> Basis:
	# Imported visual front is +Z. Test both signs and choose the one that lowers
	# the actual segment in Skeleton3D space. This avoids hard-coding left/right
	# arm signs and remains correct if the asset's arm naming/order changes.
	var axis := Vector3(0.0, 0.0, 1.0)
	var plus := Basis(axis, magnitude)
	var minus := Basis(axis, -magnitude)
	if (plus * direction).y < (minus * direction).y:
		return plus
	return minus


func _reset_global_basis_to_idle(label: String) -> void:
	var binding := _binding(label)
	if binding.is_empty():
		return
	var bone_idx: int = binding["bone_idx"]
	if not _target_idle_globals.has(bone_idx):
		return
	var baseline: Transform3D = _target_idle_globals[bone_idx]
	var current := _skeleton.get_bone_global_pose(bone_idx)
	_skeleton.set_bone_global_pose(
		bone_idx,
		Transform3D(baseline.basis, current.origin)
	)


func _binding(label: String) -> Dictionary:
	if _binding_by_label.has(label):
		return _binding_by_label[label]
	return {}
