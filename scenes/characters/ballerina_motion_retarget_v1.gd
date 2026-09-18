extends Node3D

# Phase 10.1 — mannequin-to-ballerina motion retarget v1.
#
# This first proof deliberately retargets the opening STAGE_BOW plus BALANCE.
# The accepted Phase 7/9 DancerVisual remains the choreography source of truth;
# its generated rig keeps running invisibly. During those states we sample that
# rig and transfer its global
# joint-orientation deltas onto the skinned humanoid skeleton. All gameplay,
# collision, timing, route and recovery logic remain owned by Dancer.

const RETARGET_STATES := {
	&"STAGE_BOW": true,
	&"BALANCE": true,
}

@onready var _model_root: Node3D = $low_poly_girl
@onready var _skeleton: Skeleton3D = $low_poly_girl/Rig/Skeleton3D
@onready var _animation_player: AnimationPlayer = $low_poly_girl/AnimationPlayer

var _source_visual: Node3D
var _bound := false
var _retarget_active := false
var _bindings: Array[Dictionary] = []
var _target_idle_poses: Dictionary = {}
var _target_idle_globals: Dictionary = {}


func _ready() -> void:
	process_priority = 100
	call_deferred("_try_bind")


func _process(_delta: float) -> void:
	if not _bound:
		_try_bind()
		return

	if not is_instance_valid(_source_visual):
		_bound = false
		_retarget_active = false
		return

	var state := &""
	if _source_visual.has_method("get_visual_state"):
		state = StringName(_source_visual.call("get_visual_state"))

	if RETARGET_STATES.has(state):
		if not _retarget_active:
			_animation_player.stop()
			_retarget_active = true
		_apply_idle_baseline()
		_apply_motion_retarget()
	elif _retarget_active:
		_retarget_active = false


func _try_bind() -> void:
	if _bound:
		return

	var dancer := get_parent()
	if not (dancer is CharacterBody3D):
		return

	_source_visual = dancer.get_node_or_null("DancerVisual") as Node3D
	if _source_visual == null or _skeleton == null or _animation_player == null:
		return

	_bindings = _resolve_bindings()
	if _bindings.is_empty():
		push_warning("Ballerina retarget v1 could not resolve any humanoid bones.")
		return

	_capture_idle_baseline()
	_bound = true
	print(
		"Ballerina retarget v1 ready: %d mannequin joints mapped to humanoid bones."
		% _bindings.size()
	)


func _resolve_bindings() -> Array[Dictionary]:
	var specs := [
		{
			"source": NodePath("Rig/Pelvis"),
			"aliases": ["hips", "pelvis"],
		},
		{
			"source": NodePath("Rig/Pelvis/Torso"),
			"aliases": ["chest", "upperchest", "spine2", "spine02", "spine1", "spine01", "spine"],
		},
		{
			"source": NodePath("Rig/Pelvis/Torso/Head"),
			"aliases": ["head"],
		},
		{
			"source": NodePath("Rig/Pelvis/Torso/ArmBackShoulder"),
			"aliases": ["leftupperarm", "upperarml", "leftarm", "arml"],
		},
		{
			"source": NodePath("Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow"),
			"aliases": ["leftlowerarm", "lowerarml", "leftforearm", "forearml"],
		},
		{
			"source": NodePath("Rig/Pelvis/Torso/ArmFrontShoulder"),
			"aliases": ["rightupperarm", "upperarmr", "rightarm", "armr"],
		},
		{
			"source": NodePath("Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow"),
			"aliases": ["rightlowerarm", "lowerarmr", "rightforearm", "forearmr"],
		},
		{
			"source": NodePath("Rig/Pelvis/LegBackHip"),
			"aliases": ["leftupperleg", "upperlegl", "leftupleg", "leftthigh", "thighl"],
		},
		{
			"source": NodePath("Rig/Pelvis/LegBackHip/LegBackKnee"),
			"aliases": ["leftlowerleg", "lowerlegl", "leftleg", "leftcalf", "calfl", "leftshin", "shinl"],
		},
		{
			"source": NodePath("Rig/Pelvis/LegBackHip/LegBackKnee/FootBack"),
			"aliases": ["leftfoot", "footl"],
		},
		{
			"source": NodePath("Rig/Pelvis/LegFrontHip"),
			"aliases": ["rightupperleg", "upperlegr", "rightupleg", "rightthigh", "thighr"],
		},
		{
			"source": NodePath("Rig/Pelvis/LegFrontHip/LegFrontKnee"),
			"aliases": ["rightlowerleg", "lowerlegr", "rightleg", "rightcalf", "calfr", "rightshin", "shinr"],
		},
		{
			"source": NodePath("Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront"),
			"aliases": ["rightfoot", "footr"],
		},
	]

	var resolved: Array[Dictionary] = []
	for spec in specs:
		var source_node := _source_visual.get_node_or_null(spec["source"]) as Node3D
		if source_node == null:
			continue
		var bone_idx := _find_bone(spec["aliases"])
		if bone_idx < 0:
			continue
		resolved.append({
			"source_node": source_node,
			"bone_idx": bone_idx,
		})
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

	for binding in _bindings:
		var bone_idx: int = binding["bone_idx"]
		_target_idle_poses[bone_idx] = _skeleton.get_bone_pose(bone_idx)
		_target_idle_globals[bone_idx] = _skeleton.get_bone_global_pose(bone_idx)

	if previous_animation != &"" and _animation_player.has_animation(previous_animation):
		_animation_player.play(previous_animation)
		_animation_player.seek(previous_position, true)
		if not was_playing:
			_animation_player.pause()
	else:
		_animation_player.stop()


func _apply_idle_baseline() -> void:
	for binding in _bindings:
		var bone_idx: int = binding["bone_idx"]
		if _target_idle_poses.has(bone_idx):
			_skeleton.set_bone_pose(bone_idx, _target_idle_poses[bone_idx])


func _apply_motion_retarget() -> void:
	var source_base_basis := _source_visual.global_transform.basis
	var skeleton_basis := _skeleton.global_transform.basis
	var skeleton_basis_inverse := skeleton_basis.inverse()

	for binding in _bindings:
		var source_node: Node3D = binding["source_node"]
		var bone_idx: int = binding["bone_idx"]
		if not is_instance_valid(source_node):
			continue
		if not _target_idle_globals.has(bone_idx):
			continue

		# Every joint in the accepted mannequin rig has an identity rest basis.
		# Its current world basis therefore carries the complete accumulated
		# choreography delta relative to DancerVisual's own basis.
		var source_delta_world := (
			source_node.global_transform.basis
			* source_base_basis.inverse()
		)

		var baseline_global: Transform3D = _target_idle_globals[bone_idx]
		var baseline_world_basis := skeleton_basis * baseline_global.basis
		var desired_world_basis := source_delta_world * baseline_world_basis
		var desired_skeleton_basis := skeleton_basis_inverse * desired_world_basis

		# Keep the humanoid rig's own bone positions/lengths. Only orientation is
		# transferred, so the mannequin can never change collision or proportions.
		var current_global := _skeleton.get_bone_global_pose(bone_idx)
		_skeleton.set_bone_global_pose(
			bone_idx,
			Transform3D(desired_skeleton_basis, current_global.origin)
		)
