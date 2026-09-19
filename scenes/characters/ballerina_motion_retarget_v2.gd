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
	# Full-body procedural retarget is reserved for slow stage-presentation
	# states only. Natural locomotion must stay on the imported humanoid clips.
	&"STAGE_BOW": true,
	&"STAGE_READY": true,
	&"STAGE_FINAL_BOW": true,
	&"STAGE_EXIT_TURN": true,
}

const OVERLAY_STATES := {
	# These states keep the imported RUN clip alive and add only the emergency
	# body mechanics that the stock asset does not provide.
	&"STUMBLE": true,
	&"RECOVERY": true,
}

# Native humanoid clips own ordinary locomotion: idle/walk/run/jump/landing,
# BALANCE, LOW_TRANSITION and MUSIC_* all stay on the imported rig. This is
# deliberate: the mannequin remains choreography reference, not a frame-by-frame
# puppeteer for a skeleton with different proportions and intermediate joints.

const STAGE_BOW_DURATION := 1.35
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
	else:
		_state_elapsed += delta

	if RETARGET_STATES.has(state):
		if not _retarget_active:
			_animation_player.stop()
			_retarget_active = true

		_apply_idle_baseline()
		_apply_source_root_transform()
		_apply_semantic_motion_retarget(state)
		_apply_stage_presentation_calibration(state)
		return

	# Locomotion is evaluated by the imported AnimationPlayer. This script runs
	# later in the frame (process_priority = 100), so stumble/recovery can steer
	# selected chains on top of the natural run cycle without erasing its spine,
	# clavicle, wrist, toe and secondary-body motion.
	if _retarget_active:
		_model_root.transform = _model_base_transform
		_retarget_active = false

	if OVERLAY_STATES.has(state):
		_model_root.transform = _model_base_transform
		_apply_running_trip_overlay(state)


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

		# Opening révérence was already visually accepted in Phase 10.1. Keep its
		# long-spine/T-pose-derived upper body and let only the mannequin legs
		# supply the plié. Retargeting pelvis/torso/head/arms underneath that pose
		# is what made the new opening look twisted and mechanical.
		if state == &"STAGE_BOW" or state == &"STAGE_READY":
			if (
				label == "Pelvis"
				or label == "Torso"
				or label == "Head"
				or label.begins_with("Arm")
			):
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


func _apply_running_trip_overlay(state: StringName) -> void:
	if state == &"STUMBLE":
		var t := clampf(_state_elapsed / STUMBLE_DURATION, 0.0, 1.0)
		var impact := smoothstep(0.0, 1.0, t)
		var trip_strength := 0.62 * smoothstep(0.0, 0.34, t)

		# Forward momentum survives the toe catch. The CharacterBody now eases
		# toward 58% run speed; this small counter-offset keeps the
		# visually trapped foot near the obstacle while the CoM pitches past it.
		_model_root.position += Vector3(
			-0.075 * impact,
			-0.5 * 9.81 * pow(minf(t, 0.24), 2.0) * 0.23,
			0.0
		)

		# Trunk: CoM continues +X while the head counter-extends to preserve the
		# horizon. A small Z component prevents a perfectly planar mannequin fall.
		_steer_current_chain_world_direction(
			"Pelvis",
			"Torso",
			Vector3(0.62, 0.77, -0.10).lerp(
				Vector3(0.18, 0.98, 0.0),
				1.0 - impact
			).normalized(),
			trip_strength
		)
		_steer_current_chain_world_direction(
			"Torso",
			"Head",
			Vector3(0.20, 0.98, 0.02).normalized(),
			trip_strength
		)

		# Right/front foot is the tripping foot. It is caught in front of the CoM
		# while the left/back leg is stranded behind and cannot rescue the first
		# impact in time.
		_steer_current_chain_world_direction(
			"LegFrontHip",
			"LegFrontKnee",
			Vector3(0.38, -0.92, -0.02).normalized(),
			trip_strength
		)
		_steer_current_chain_world_direction(
			"LegFrontKnee",
			"FootFront",
			Vector3(0.08, -0.995, 0.0).normalized(),
			trip_strength
		)
		_steer_current_chain_world_direction(
			"LegBackHip",
			"LegBackKnee",
			Vector3(-0.38, -0.92, 0.08).normalized(),
			trip_strength
		)
		_steer_current_chain_world_direction(
			"LegBackKnee",
			"FootBack",
			Vector3(-0.12, -0.99, 0.04).normalized(),
			trip_strength
		)

		# Reflex brace: both arms thrust forward, but asymmetrically. The right
		# elbow folds more sharply; the left arm opens laterally for counter-torque.
		_steer_current_chain_world_direction(
			"ArmFrontShoulder",
			"ArmFrontElbow",
			Vector3(0.90, -0.28, -0.25).normalized(),
			trip_strength
		)
		_steer_current_segment_world_direction(
			_binding_index("ArmFrontElbow"),
			_right_hand_idx,
			Vector3(0.05, -0.96, -0.28).normalized(),
			trip_strength
		)
		_steer_current_chain_world_direction(
			"ArmBackShoulder",
			"ArmBackElbow",
			Vector3(0.76, -0.38, 0.52).normalized(),
			trip_strength
		)
		_steer_current_segment_world_direction(
			_binding_index("ArmBackElbow"),
			_left_hand_idx,
			Vector3(0.42, -0.78, 0.46).normalized(),
			trip_strength
		)

		# Dorsiflex the caught forefoot if the imported rig exposes a toe/ball bone.
		_steer_current_segment_world_direction(
			_binding_index("FootFront"),
			_right_toe_idx,
			Vector3(0.98, 0.18, 0.0).normalized(),
			trip_strength
		)
		return

	if state != &"RECOVERY":
		return

	var t := clampf(_state_elapsed / RECOVERY_DURATION, 0.0, 1.0)
	var release := smoothstep(0.0, 1.0, t)
	var custom_strength := 0.60 * (1.0 - smoothstep(0.52, 0.92, t))

	# The body is still forward of the original support base at recovery start.
	# Return the counter-offset gradually while adding a small rebound rather than
	# teleporting the visual root back onto the gameplay capsule.
	var rebound := 0.030 * sin(PI * clampf((t - 0.22) / 0.60, 0.0, 1.0))
	_model_root.position += Vector3(
		-0.075 * (1.0 - release),
		-0.032 * (1.0 - release) + rebound,
		0.0
	)

	# Emergency step. The caught right foot unhooks and trails; the free left leg
	# drives high and forward to get a foot back in front of the falling CoM.
	var torso_dir := Vector3(0.60, 0.79, -0.08).lerp(
		Vector3(0.10, 0.995, 0.0),
		release
	).normalized()
	var head_dir := Vector3(0.18, 0.98, 0.02).lerp(
		Vector3(0.02, 1.0, 0.0),
		release
	).normalized()
	_steer_current_chain_world_direction("Pelvis", "Torso", torso_dir, custom_strength)
	_steer_current_chain_world_direction("Torso", "Head", head_dir, custom_strength)

	var left_thigh := Vector3(0.50, -0.84, 0.08).lerp(
		Vector3(0.24, -0.97, 0.02),
		smoothstep(0.28, 0.72, t)
	).normalized()
	var left_shin := Vector3(0.32, -0.94, 0.05).lerp(
		Vector3(0.08, -0.997, 0.0),
		smoothstep(0.30, 0.76, t)
	).normalized()
	_steer_current_chain_world_direction(
		"LegBackHip",
		"LegBackKnee",
		left_thigh,
		custom_strength
	)
	_steer_current_chain_world_direction(
		"LegBackKnee",
		"FootBack",
		left_shin,
		custom_strength
	)

	var right_thigh := Vector3(-0.34, -0.94, -0.02).lerp(
		Vector3(0.18, -0.98, -0.01),
		smoothstep(0.22, 0.80, t)
	).normalized()
	var right_shin := Vector3(-0.14, -0.99, 0.0).lerp(
		Vector3(0.02, -1.0, 0.0),
		smoothstep(0.25, 0.82, t)
	).normalized()
	_steer_current_chain_world_direction(
		"LegFrontHip",
		"LegFrontKnee",
		right_thigh,
		custom_strength
	)
	_steer_current_chain_world_direction(
		"LegFrontKnee",
		"FootFront",
		right_shin,
		custom_strength
	)

	# Asymmetric arm recovery generates counter-torque instead of a mirrored
	# cartoon flail. The override fades before RECOVERY ends so the accepted
	# run-cycle brush/contact can reconnect without a visible pop.
	_steer_current_chain_world_direction(
		"ArmFrontShoulder",
		"ArmFrontElbow",
		Vector3(0.66, -0.66, -0.28).lerp(
			Vector3(0.32, -0.92, -0.18),
			release
		).normalized(),
		custom_strength
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmFrontElbow"),
		_right_hand_idx,
		Vector3(0.25, -0.94, -0.22).normalized(),
		custom_strength
	)
	_steer_current_chain_world_direction(
		"ArmBackShoulder",
		"ArmBackElbow",
		Vector3(-0.24, -0.72, 0.65).lerp(
			Vector3(0.22, -0.95, 0.20),
			release
		).normalized(),
		custom_strength
	)
	_steer_current_segment_world_direction(
		_binding_index("ArmBackElbow"),
		_left_hand_idx,
		Vector3(0.05, -0.90, 0.43).normalized(),
		custom_strength
	)

	# Once the trapped foot releases, return from dorsiflexion toward a pointed
	# travelling foot before handing control fully back to the source recovery.
	_steer_current_segment_world_direction(
		_binding_index("FootFront"),
		_right_toe_idx,
		Vector3(0.98, -0.18, 0.0).normalized(),
		custom_strength
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
			# Restore the accepted Phase 10.1 opening curtsy exactly: the dancer
			# turns to +Z through the source Rig, keeps a long torso, opens the
			# arms from her own T-pose morphology and lets the legs provide plié.
			var phase := clampf(_state_elapsed / STAGE_BOW_DURATION, 0.0, 1.0)
			_apply_classical_reverence_upper_body(phase, false)
		&"STAGE_READY":
			_apply_classical_reverence_upper_body(1.0, false)
		&"STAGE_FINAL_BOW":
			# Final bow intentionally remains untouched in this pass.
			pass


func _apply_classical_reverence_upper_body(phase: float, final_reverence: bool) -> void:
	if final_reverence:
		return

	# Accepted Phase 10.1 female révérence: curtsy + port de bras, not a torso
	# bow. The motion descends and rises once, while the arms settle into the
	# calm open ready position used before the run begins.
	var depth := sin(clampf(phase, 0.0, 1.0) * PI)
	var open_t := smoothstep(0.0, 0.32, phase)

	_model_root.position.y = _model_base_transform.origin.y - 0.055 * depth

	var upper_angle := lerpf(1.02, 0.42, open_t)
	var lower_angle := upper_angle + 0.16
	_apply_accepted_reverence_arm("ArmBackShoulder", upper_angle)
	_apply_accepted_reverence_arm("ArmBackElbow", lower_angle)
	_apply_accepted_reverence_arm("ArmFrontShoulder", -upper_angle)
	_apply_accepted_reverence_arm("ArmFrontElbow", -lower_angle)

	_apply_accepted_reverence_body("Torso", 0.045 * depth)
	_apply_accepted_reverence_body("Head", 0.13 * depth)


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
