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
	&"STAGE_READY": true,
	&"STAGE_FINAL_BOW": true,
	&"BALANCE": true,
}

const FRONT_FACING_STATES := {
	&"STAGE_BOW": true,
	&"STAGE_READY": true,
	&"STAGE_FINAL_BOW": true,
}

# Pas de Run stage geometry: gameplay travels along +X. The audience is exactly
# 90 degrees to the dancer's RIGHT, i.e. +Z in world space.
const TRAVEL_DIRECTION := Vector3.RIGHT
const AUDIENCE_DIRECTION := Vector3(0.0, 0.0, 1.0)

@onready var _model_root: Node3D = $low_poly_girl
@onready var _skeleton: Skeleton3D = $low_poly_girl/Rig/Skeleton3D
@onready var _animation_player: AnimationPlayer = $low_poly_girl/AnimationPlayer

var _source_visual: Node3D
var _source_rig: Node3D
var _model_base_transform: Transform3D
var _bound := false
var _retarget_active := false
var _bindings: Array[Dictionary] = []
var _target_idle_poses: Dictionary = {}
var _target_idle_globals: Dictionary = {}
var _target_bow_arm_poses: Dictionary = {}
var _target_bow_arm_globals: Dictionary = {}


func _ready() -> void:
	process_priority = 100
	_model_base_transform = _model_root.transform
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

		# The source mannequin choreography changes every frame. Retarget the
		# current pose continuously for the full state instead of freezing on the
		# first frame seen at state entry.
		_apply_state_baseline(state)
		_apply_motion_retarget(state)
	elif _retarget_active:
		_model_root.transform = _model_base_transform
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

	_source_rig = _source_visual.get_node_or_null("Rig") as Node3D
	if _source_rig == null:
		return

	_bindings = _resolve_bindings()
	if _bindings.is_empty():
		push_warning("Ballerina retarget v1 could not resolve any humanoid bones.")
		return

	_capture_idle_baseline()
	_capture_bow_arm_baseline()
	_bound = true
	print(
		"Ballerina retarget v1 ready: %d mannequin joints mapped to humanoid bones."
		% _bindings.size()
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
			continue
		var bone_idx := _find_bone(spec["aliases"])
		if bone_idx < 0:
			print(
				"Ballerina retarget unresolved: %s"
				% String(spec["label"])
			)
			continue
		print(
			"Ballerina retarget map: %s -> %s"
			% [
				String(spec["label"]),
				String(_skeleton.get_bone_name(bone_idx)),
			]
		)
		resolved.append({
			"label": String(spec["label"]),
			"source_node": source_node,
			"bone_idx": bone_idx,
		})

	if resolved.size() < specs.size():
		var bone_names: Array[String] = []
		for bone_idx in range(_skeleton.get_bone_count()):
			bone_names.append(String(_skeleton.get_bone_name(bone_idx)))
		print("Ballerina skeleton bones: %s" % ", ".join(bone_names))

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


func _capture_bow_arm_baseline() -> void:
	# The imported idle pose keeps this low-poly character's arms very close to
	# the torso. The mannequin's front-facing bow also relied on mannequin-only
	# shoulder spacing, which a skinned humanoid cannot inherit as joint
	# positions. Use the model's own T-Pose arm orientation as the morphological
	# reference for STAGE_BOW, while the mannequin still supplies the motion.
	if not _animation_player.has_animation("T-Pose"):
		return

	var previous_animation := _animation_player.current_animation
	var previous_position := _animation_player.current_animation_position
	var was_playing := _animation_player.is_playing()

	_animation_player.play("T-Pose")
	_animation_player.seek(0.0, true)
	_animation_player.advance(0.0)

	for binding in _bindings:
		if not _is_arm_binding(binding):
			continue
		var bone_idx: int = binding["bone_idx"]
		_target_bow_arm_poses[bone_idx] = _skeleton.get_bone_pose(bone_idx)
		_target_bow_arm_globals[bone_idx] = _skeleton.get_bone_global_pose(bone_idx)

	if previous_animation != &"" and _animation_player.has_animation(previous_animation):
		_animation_player.play(previous_animation)
		_animation_player.seek(previous_position, true)
		if not was_playing:
			_animation_player.pause()
	else:
		_animation_player.stop()


func _is_arm_binding(binding: Dictionary) -> bool:
	return String(binding.get("label", "")).begins_with("Arm")


func _apply_state_baseline(state: StringName) -> void:
	_apply_idle_baseline()

	# Stage orientation is relative to travel, never inferred from camera yaw.
	# Travel is +X; dancer-right is +Z. Restore the accepted gameplay transform,
	# then aim the imported model's visual +Z front exactly along +Z.
	_model_root.transform = _model_base_transform
	if FRONT_FACING_STATES.has(state):
		_model_root.look_at(
			_model_root.global_position + AUDIENCE_DIRECTION,
			Vector3.UP,
			true
		)

	if state != &"STAGE_BOW":
		return

	for binding in _bindings:
		if not _is_arm_binding(binding):
			continue
		var bone_idx: int = binding["bone_idx"]
		if _target_bow_arm_poses.has(bone_idx):
			_skeleton.set_bone_pose(bone_idx, _target_bow_arm_poses[bone_idx])


func _apply_idle_baseline() -> void:
	for binding in _bindings:
		var bone_idx: int = binding["bone_idx"]
		if _target_idle_poses.has(bone_idx):
			_skeleton.set_bone_pose(bone_idx, _target_idle_poses[bone_idx])


func _apply_motion_retarget(state: StringName) -> void:
	var source_rig_basis := _source_rig.global_transform.basis
	var source_rig_basis_inverse := source_rig_basis.inverse()
	var skeleton_basis := _skeleton.global_transform.basis
	var skeleton_basis_inverse := skeleton_basis.inverse()

	for binding in _bindings:
		var source_node: Node3D = binding["source_node"]
		var bone_idx: int = binding["bone_idx"]
		if not is_instance_valid(source_node):
			continue
		if not _target_idle_globals.has(bone_idx):
			continue

		# Retarget joint articulation relative to the mannequin Rig itself.
		# STAGE_BOW rotates that entire source Rig by 90 degrees for presentation;
		# including that root yaw here would apply the stage turn a second time
		# through every target bone. Root orientation is handled separately above.
		var source_delta_in_rig := (
			source_rig_basis_inverse
			* source_node.global_transform.basis
		)

		var baseline_global: Transform3D = _target_idle_globals[bone_idx]
		if (
			state == &"STAGE_BOW"
			and _is_arm_binding(binding)
			and _target_bow_arm_globals.has(bone_idx)
		):
			baseline_global = _target_bow_arm_globals[bone_idx]
		var desired_world_basis := skeleton_basis * source_delta_in_rig * baseline_global.basis
		var desired_skeleton_basis := skeleton_basis_inverse * desired_world_basis

		# Keep the humanoid rig's own bone positions/lengths. Only orientation is
		# transferred, so the mannequin can never change collision or proportions.
		var current_global := _skeleton.get_bone_global_pose(bone_idx)
		_skeleton.set_bone_global_pose(
			bone_idx,
			Transform3D(desired_skeleton_basis, current_global.origin)
		)
