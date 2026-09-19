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
	&"NEUTRAL": true,
	&"STAGE_WALK": true,
	&"STAGE_BOW": true,
	&"STAGE_READY": true,
	&"STAGE_FINAL_BOW": true,
	&"STAGE_EXIT_TURN": true,
	&"TRAVEL": true,
	&"JUMP": true,
	&"AIRBORNE": true,
	&"LANDING": true,
	&"LOW_TRANSITION": true,
	&"BALANCE": true,
	&"STUMBLE": true,
	&"RECOVERY": true,
	&"MUSIC_FLOW": true,
	&"MUSIC_BUILD": true,
	&"MUSIC_RELEASE": true,
	&"MUSIC_PULSE": true,
	&"MUSIC_CLIMAX": true,
	&"MUSIC_PREP": true,
	&"MUSIC_ACCENT": true,
}

# BALANCE is intentionally kept as a state but dancer_visual_motion_v5 maps its
# animation to the travelling run cycle. Pas de Run is always-run: balance only
# adds lateral Z drift/recentering and never changes the dancer into a stationary
# pose.

const STAGE_BOW_DURATION := 1.35
const STAGE_BOW_TURN_TIME := 0.28
const STAGE_FINAL_BOW_DURATION := 2.60
const STAGE_FINAL_TURN_TIME := 0.32

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

	if not RETARGET_STATES.has(state):
		if _retarget_active:
			_model_root.transform = _model_base_transform
			_retarget_active = false
		return

	if not _retarget_active:
		_animation_player.stop()
		_retarget_active = true

	_apply_idle_baseline()
	_apply_source_root_transform()
	_apply_semantic_motion_retarget()
	_apply_stage_presentation_calibration(state)


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


func _apply_semantic_motion_retarget() -> void:
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
		if not is_instance_valid(source_node):
			continue
		if not _target_idle_globals.has(bone_idx):
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


func _apply_stage_presentation_calibration(state: StringName) -> void:
	match state:
		&"STAGE_BOW":
			var bow_phase := clampf(
				(_state_elapsed - STAGE_BOW_TURN_TIME)
				/ (STAGE_BOW_DURATION - STAGE_BOW_TURN_TIME),
				0.0,
				1.0
			)
			_apply_classical_reverence_upper_body(sin(bow_phase * PI), false)
		&"STAGE_READY":
			_apply_classical_reverence_upper_body(0.0, false)
		&"STAGE_FINAL_BOW":
			var final_phase := clampf(
				(_state_elapsed - STAGE_FINAL_TURN_TIME)
				/ (STAGE_FINAL_BOW_DURATION - STAGE_FINAL_TURN_TIME),
				0.0,
				1.0
			)
			_apply_classical_reverence_upper_body(smoothstep(0.0, 1.0, final_phase), true)


func _apply_classical_reverence_upper_body(depth: float, final_reverence: bool) -> void:
	# Female classical révérence is a curtsey with port de bras, not a male-style
	# torso fold. Keep the trunk long and let the leg/plié articulation carry the
	# acknowledgement. The hidden mannequin still supplies the lower-body timing.
	_reset_global_basis_to_idle("Torso")
	_reset_global_basis_to_idle("Head")

	if not _tpose_available:
		return

	var shoulder_drop := 0.34 + depth * (0.16 if final_reverence else 0.10)
	var elbow_drop := shoulder_drop + 0.12

	_apply_lowered_tpose_chain(
		"ArmBackShoulder",
		"ArmBackElbow",
		_left_hand_idx,
		shoulder_drop,
		elbow_drop
	)
	_apply_lowered_tpose_chain(
		"ArmFrontShoulder",
		"ArmFrontElbow",
		_right_hand_idx,
		shoulder_drop,
		elbow_drop
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
