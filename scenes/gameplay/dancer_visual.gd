extends Node3D

signal visual_state_changed(state: StringName)

const STATE_NEUTRAL := &"NEUTRAL"
const STATE_STAGE_WALK := &"STAGE_WALK"
const STATE_STAGE_BOW := &"STAGE_BOW"
const STATE_STAGE_READY := &"STAGE_READY"
const STATE_STAGE_FINAL_BOW := &"STAGE_FINAL_BOW"
const STATE_TRAVEL := &"TRAVEL"
const STATE_JUMP := &"JUMP"
const STATE_AIRBORNE := &"AIRBORNE"
const STATE_LANDING := &"LANDING"
const STATE_LOW_TRANSITION := &"LOW_TRANSITION"
const STATE_BALANCE := &"BALANCE"
const STATE_STUMBLE := &"STUMBLE"
const STATE_RECOVERY := &"RECOVERY"
const STATE_MUSIC_FLOW := &"MUSIC_FLOW"
const STATE_MUSIC_BUILD := &"MUSIC_BUILD"
const STATE_MUSIC_RELEASE := &"MUSIC_RELEASE"
const STATE_MUSIC_PULSE := &"MUSIC_PULSE"
const STATE_MUSIC_CLIMAX := &"MUSIC_CLIMAX"
const STATE_MUSIC_PREP := &"MUSIC_PREP"
const STATE_MUSIC_ACCENT := &"MUSIC_ACCENT"

const MUSIC_ACCENT_VISUAL_TIME := 0.22

const VISUAL_STATES := [
	STATE_NEUTRAL,
	STATE_STAGE_WALK,
	STATE_STAGE_BOW,
	STATE_STAGE_READY,
	STATE_STAGE_FINAL_BOW,
	STATE_TRAVEL,
	STATE_JUMP,
	STATE_AIRBORNE,
	STATE_LANDING,
	STATE_LOW_TRANSITION,
	STATE_BALANCE,
	STATE_STUMBLE,
	STATE_RECOVERY,
	STATE_MUSIC_FLOW,
	STATE_MUSIC_BUILD,
	STATE_MUSIC_RELEASE,
	STATE_MUSIC_PULSE,
	STATE_MUSIC_CLIMAX,
	STATE_MUSIC_PREP,
	STATE_MUSIC_ACCENT,
]

const TAKEOFF_VISUAL_TIME := 0.16
const LANDING_VISUAL_TIME := 0.22

const TRACK_PATHS := [
	"Rig:position",
	"Rig:rotation",
	"Rig/Pelvis:rotation",
	"Rig/Pelvis/Torso:rotation",
	"Rig/Pelvis/Torso/Head:rotation",
	"Rig/Pelvis/Torso/ArmBackShoulder:rotation",
	"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation",
	"Rig/Pelvis/Torso/ArmFrontShoulder:rotation",
	"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation",
	"Rig/Pelvis/LegBackHip:rotation",
	"Rig/Pelvis/LegBackHip/LegBackKnee:rotation",
	"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation",
	"Rig/Pelvis/LegFrontHip:rotation",
	"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation",
	"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation",
]

var dancer: CharacterBody3D
var _rig: Node3D
var _animation_player: AnimationPlayer
var _animation_tree: AnimationTree
var _state_machine: AnimationNodeStateMachine
var _playback: AnimationNodeStateMachinePlayback

var _current_state: StringName = STATE_NEUTRAL
var _was_on_floor := true
var _airborne_time := 0.0
var _landing_time := 0.0

var _stage_presentation_state: StringName = &""
var _music_expression_enabled := false
var _music_phrase_state: StringName = STATE_MUSIC_FLOW
var _music_preparing_action: StringName = &""
var _music_accent_remaining := 0.0


func _ready() -> void:
	dancer = get_parent() as CharacterBody3D
	if dancer == null:
		push_error("DancerVisual must be a direct child of Dancer CharacterBody3D.")
		set_physics_process(false)
		return

	_build_rig()
	_build_animation_system()
	_was_on_floor = dancer.is_on_floor()
	_set_visual_state(STATE_NEUTRAL, true)


func _physics_process(delta: float) -> void:
	if dancer == null:
		return
	_music_accent_remaining = maxf(_music_accent_remaining - delta, 0.0)
	_set_visual_state(_resolve_visual_state(delta))


func set_stage_presentation_state(stage: StringName) -> void:
	var next_state := &""
	match stage:
		&"WALK":
			next_state = STATE_STAGE_WALK
		&"BOW":
			next_state = STATE_STAGE_BOW
		&"READY":
			next_state = STATE_STAGE_READY
		&"FINAL_BOW":
			next_state = STATE_STAGE_FINAL_BOW
		_:
			return
	if _stage_presentation_state == next_state:
		return
	_stage_presentation_state = next_state
	_set_visual_state(next_state)


func clear_stage_presentation() -> void:
	_stage_presentation_state = &""


func set_music_expression_enabled(enabled: bool) -> void:
	_music_expression_enabled = enabled
	if not enabled:
		_music_preparing_action = &""
		_music_accent_remaining = 0.0


func set_music_phrase_role(role: StringName) -> void:
	match role:
		&"BUILD":
			_music_phrase_state = STATE_MUSIC_BUILD
		&"RELEASE":
			_music_phrase_state = STATE_MUSIC_RELEASE
		&"PULSE", &"TURNING_POINT":
			_music_phrase_state = STATE_MUSIC_PULSE
		&"CLIMAX":
			_music_phrase_state = STATE_MUSIC_CLIMAX
		_:
			_music_phrase_state = STATE_MUSIC_FLOW


func set_music_action_preparation(action: StringName, active: bool) -> void:
	if active:
		_music_preparing_action = action
	elif _music_preparing_action == action:
		_music_preparing_action = &""


func trigger_music_accent() -> void:
	_music_accent_remaining = MUSIC_ACCENT_VISUAL_TIME


func get_visual_state() -> StringName:
	return _current_state


func _resolve_visual_state(delta: float) -> StringName:
	if _stage_presentation_state != &"":
		return _stage_presentation_state

	if dancer.get("has_fallen") == true:
		return _current_state

	var locomotion := &"NORMAL"
	if dancer.has_method("get_locomotion_state"):
		locomotion = StringName(dancer.call("get_locomotion_state"))

	if locomotion == STATE_STUMBLE:
		return STATE_STUMBLE
	if locomotion == STATE_RECOVERY:
		return STATE_RECOVERY
	if dancer.get("in_low_transition") == true:
		return STATE_LOW_TRANSITION
	if dancer.get("in_balance_zone") == true:
		return STATE_BALANCE

	var grounded := dancer.is_on_floor()
	if not grounded:
		if _was_on_floor:
			_airborne_time = 0.0
		_airborne_time += delta
		_landing_time = 0.0
		_was_on_floor = false
		if dancer.velocity.y > 0.15 and _airborne_time <= TAKEOFF_VISUAL_TIME:
			return STATE_JUMP
		return STATE_AIRBORNE

	if not _was_on_floor:
		_landing_time = LANDING_VISUAL_TIME
		_airborne_time = 0.0
	_was_on_floor = true

	if _landing_time > 0.0:
		_landing_time = maxf(_landing_time - delta, 0.0)
		return STATE_LANDING

	if not _music_expression_enabled:
		return STATE_TRAVEL
	if _music_preparing_action == &"JUMP":
		return STATE_MUSIC_PREP
	if _music_accent_remaining > 0.0:
		return STATE_MUSIC_ACCENT
	return _music_phrase_state


func _set_visual_state(state: StringName, force := false) -> void:
	if not force and state == _current_state:
		return
	_current_state = state
	if _playback != null:
		if force:
			_playback.start(state, true)
		else:
			_playback.travel(state)
	visual_state_changed.emit(state)


func _build_rig() -> void:
	_rig = Node3D.new()
	_rig.name = "Rig"
	add_child(_rig)

	var costume := StandardMaterial3D.new()
	costume.albedo_color = Color(0.30, 0.075, 0.12, 1.0)
	costume.roughness = 0.72

	var skin := StandardMaterial3D.new()
	skin.albedo_color = Color(0.78, 0.61, 0.52, 1.0)
	skin.roughness = 0.82

	var slipper := StandardMaterial3D.new()
	slipper.albedo_color = Color(0.78, 0.61, 0.58, 1.0)
	slipper.roughness = 0.78

	var pelvis := _joint(_rig, "Pelvis", Vector3(0.0, -0.12, 0.0))
	_box(pelvis, "PelvisShape", Vector3(0.28, 0.18, 0.20), Vector3(0.0, -0.01, 0.0), costume)

	var torso := _joint(pelvis, "Torso", Vector3(0.0, 0.10, 0.0))
	_box(torso, "TorsoShape", Vector3(0.34, 0.56, 0.19), Vector3(0.0, 0.28, 0.0), costume)

	var head := _joint(torso, "Head", Vector3(0.0, 0.68, 0.0))
	_sphere(head, "HeadShape", 0.15, skin)

	var arm_back := _joint(torso, "ArmBackShoulder", Vector3(-0.02, 0.52, 0.085))
	_capsule(arm_back, "ArmBackUpper", 0.36, 0.055, skin)
	var elbow_back := _joint(arm_back, "ArmBackElbow", Vector3(0.0, -0.34, 0.0))
	_capsule(elbow_back, "ArmBackLower", 0.32, 0.048, skin)

	var arm_front := _joint(torso, "ArmFrontShoulder", Vector3(0.02, 0.52, -0.085))
	_capsule(arm_front, "ArmFrontUpper", 0.36, 0.055, skin)
	var elbow_front := _joint(arm_front, "ArmFrontElbow", Vector3(0.0, -0.34, 0.0))
	_capsule(elbow_front, "ArmFrontLower", 0.32, 0.048, skin)

	var leg_back := _joint(pelvis, "LegBackHip", Vector3(-0.045, -0.08, 0.055))
	_capsule(leg_back, "LegBackUpper", 0.48, 0.075, skin)
	var knee_back := _joint(leg_back, "LegBackKnee", Vector3(0.0, -0.44, 0.0))
	_capsule(knee_back, "LegBackLower", 0.44, 0.062, skin)
	var foot_back := _joint(knee_back, "FootBack", Vector3(0.0, -0.42, 0.0))
	_box(foot_back, "FootBackShape", Vector3(0.24, 0.07, 0.10), Vector3(0.10, -0.02, 0.0), slipper)

	var leg_front := _joint(pelvis, "LegFrontHip", Vector3(0.045, -0.08, -0.055))
	_capsule(leg_front, "LegFrontUpper", 0.48, 0.075, skin)
	var knee_front := _joint(leg_front, "LegFrontKnee", Vector3(0.0, -0.44, 0.0))
	_capsule(knee_front, "LegFrontLower", 0.44, 0.062, skin)
	var foot_front := _joint(knee_front, "FootFront", Vector3(0.0, -0.42, 0.0))
	_box(foot_front, "FootFrontShape", Vector3(0.24, 0.07, 0.10), Vector3(0.10, -0.02, 0.0), slipper)


func _joint(parent: Node3D, node_name: String, local_position: Vector3) -> Node3D:
	var joint := Node3D.new()
	joint.name = node_name
	joint.position = local_position
	parent.add_child(joint)
	return joint


func _capsule(parent: Node3D, node_name: String, length: float, radius: float, material: Material) -> void:
	var mesh := CapsuleMesh.new()
	mesh.height = length
	mesh.radius = radius
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = material
	instance.position.y = -length * 0.5
	parent.add_child(instance)


func _box(parent: Node3D, node_name: String, size: Vector3, local_position: Vector3, material: Material) -> void:
	var mesh := BoxMesh.new()
	mesh.size = size
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = material
	instance.position = local_position
	parent.add_child(instance)


func _sphere(parent: Node3D, node_name: String, radius: float, material: Material) -> void:
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = material
	parent.add_child(instance)


func _build_animation_system() -> void:
	_animation_player = AnimationPlayer.new()
	_animation_player.name = "AnimationPlayer"
	_animation_player.root_node = NodePath("..")
	add_child(_animation_player)

	var library := AnimationLibrary.new()
	_add_animation(library, "neutral", _neutral_animation())
	_add_animation(library, "stage_walk", _stage_walk_animation())
	_add_animation(library, "stage_bow", _stage_bow_animation())
	_add_animation(library, "stage_ready", _stage_ready_animation())
	_add_animation(library, "stage_final_bow", _stage_final_bow_animation())
	_add_animation(library, "travel", _travel_animation())
	_add_animation(library, "jump", _jump_animation())
	_add_animation(library, "airborne", _airborne_animation())
	_add_animation(library, "landing", _landing_animation())
	_add_animation(library, "low_transition", _low_transition_animation())
	_add_animation(library, "balance", _balance_animation())
	_add_animation(library, "stumble", _stumble_animation())
	_add_animation(library, "recovery", _recovery_animation())
	_add_animation(library, "music_flow", _music_flow_animation())
	_add_animation(library, "music_build", _music_build_animation())
	_add_animation(library, "music_release", _music_release_animation())
	_add_animation(library, "music_pulse", _music_pulse_animation())
	_add_animation(library, "music_climax", _music_climax_animation())
	_add_animation(library, "music_prep", _music_prep_animation())
	_add_animation(library, "music_accent", _music_accent_animation())
	_animation_player.add_animation_library(&"", library)

	_state_machine = AnimationNodeStateMachine.new()
	for state in VISUAL_STATES:
		var animation_node := AnimationNodeAnimation.new()
		animation_node.animation = StringName(String(state).to_lower())
		_state_machine.add_node(state, animation_node)

	for from_state in VISUAL_STATES:
		for to_state in VISUAL_STATES:
			if from_state == to_state:
				continue
			var transition := AnimationNodeStateMachineTransition.new()
			transition.xfade_time = _blend_time(from_state, to_state)
			transition.reset = true
			_state_machine.add_transition(from_state, to_state, transition)

	_animation_tree = AnimationTree.new()
	_animation_tree.name = "AnimationTree"
	add_child(_animation_tree)
	_animation_tree.anim_player = _animation_tree.get_path_to(_animation_player)
	_animation_tree.tree_root = _state_machine
	_animation_tree.active = true
	_playback = _animation_tree.get("parameters/playback") as AnimationNodeStateMachinePlayback


func _music_flow_animation() -> Animation:
	return _travel_animation()


func _music_build_animation() -> Animation:
	return _travel_animation()


func _music_release_animation() -> Animation:
	return _travel_animation()


func _music_pulse_animation() -> Animation:
	return _travel_animation()


func _music_climax_animation() -> Animation:
	return _travel_animation()


func _music_prep_animation() -> Animation:
	return _travel_animation()


func _music_accent_animation() -> Animation:
	return _travel_animation()


func _add_animation(library: AnimationLibrary, animation_name: String, animation: Animation) -> void:
	var error := library.add_animation(StringName(animation_name), animation)
	if error != OK:
		push_error("Unable to add dancer animation: %s" % animation_name)


func _blend_time(from_state: StringName, to_state: StringName) -> float:
	if to_state == STATE_MUSIC_ACCENT or from_state == STATE_MUSIC_ACCENT:
		return 0.04
	if to_state == STATE_MUSIC_PREP:
		return 0.06
	if from_state == STATE_MUSIC_PREP:
		return 0.05
	if from_state == STATE_STUMBLE or to_state == STATE_STUMBLE:
		return 0.06
	if from_state == STATE_RECOVERY or to_state == STATE_RECOVERY:
		return 0.10
	if to_state == STATE_LANDING:
		return 0.07
	if to_state == STATE_JUMP:
		return 0.06
	return 0.12


func _stage_walk_animation() -> Animation:
	return _animation_from_poses(0.96, [0.0, 0.24, 0.48, 0.72, 0.96], [
		_stage_walk_pose(1.0),
		_stage_walk_pose(0.0),
		_stage_walk_pose(-1.0),
		_stage_walk_pose(0.0),
		_stage_walk_pose(1.0),
	], true)


func _stage_walk_pose(direction: float) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, -0.010, 0.0),
		"Rig:rotation": _ry(-0.72),
		"Rig/Pelvis:rotation": _rz(-0.008 * direction),
		"Rig/Pelvis/Torso:rotation": _rz(-0.010),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.010),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.16),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.12),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.16),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.12),
		"Rig/Pelvis/LegBackHip:rotation": _rz(0.20 * direction),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.16),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.06),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(-0.20 * direction),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.16),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.06),
	})


func _stage_bow_animation() -> Animation:
	# Enter in profile, turn deliberately to the fourth wall, then offer a light
	# standing reverence before settling into the ready pose.
	return _animation_from_poses(1.35, [0.0, 0.28, 0.68, 0.94, 1.35], [
		_stage_fourth_wall_turn_pose(-0.72),
		_stage_ready_pose(),
		_pose({
			"Rig:position": Vector3(0.0, -0.045, 0.0),
			"Rig/Pelvis:rotation": _rz(-0.08),
			"Rig/Pelvis/Torso:rotation": _rz(-0.48),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.16),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.34),
			"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.18),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.34),
			"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.18),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.10),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.30),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.10),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.30),
		}),
		_pose({
			"Rig:position": Vector3(0.0, -0.060, 0.0),
			"Rig/Pelvis:rotation": _rz(-0.10),
			"Rig/Pelvis/Torso:rotation": _rz(-0.58),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.18),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.40),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.40),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.12),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.34),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.12),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.34),
		}),
		_stage_ready_pose(),
		_stage_ready_pose(),
	], false)


func _stage_fourth_wall_turn_pose(heading_y: float) -> Dictionary:
	var pose := _stage_ready_pose()
	pose["Rig:rotation"] = _ry(heading_y)
	return pose


func _stage_final_bow_animation() -> Animation:
	# Final ceremony: turn to the audience, lower onto one knee, open the arms,
	# and finish in a deeper sustained reverence.
	return _animation_from_poses(
		2.60,
		[0.0, 0.32, 0.78, 1.30, 1.95, 2.60],
		[
			_stage_fourth_wall_turn_pose(0.48),
			_stage_ready_pose(),
			_final_kneel_pose(-0.18, -0.16, 0.62),
			_final_kneel_pose(-0.29, -0.38, 0.92),
			_final_kneel_pose(-0.34, -0.58, 1.08),
			_final_kneel_pose(-0.34, -0.58, 1.08),
		],
		false
	)


func _final_kneel_pose(
	root_drop: float,
	torso_bow: float,
	arm_open: float
) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, root_drop, 0.0),
		"Rig:rotation": _ry(0.0),
		"Rig/Pelvis:rotation": _rz(-0.035),
		"Rig/Pelvis/Torso:rotation": _rz(torso_bow),
		"Rig/Pelvis/Torso/Head:rotation": _rz(-torso_bow * 0.30),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-arm_open),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.22),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(arm_open),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.22),
		# Front leg remains the supporting foot while the back knee folds down.
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.18),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(-0.42),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(0.20),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.52),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(-1.30),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(0.52),
	})


func _stage_ready_animation() -> Animation:
	return _animation_from_poses(1.8, [0.0, 0.9, 1.8], [
		_stage_ready_pose(),
		_stage_ready_breath_pose(),
		_stage_ready_pose(),
	], true)


func _stage_ready_pose() -> Dictionary:
	return _pose({
		"Rig/Pelvis/Torso:rotation": _rz(-0.012),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.015),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.24),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.18),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.24),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.18),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.04),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.10),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.04),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.10),
	})


func _stage_ready_breath_pose() -> Dictionary:
	var pose := _stage_ready_pose()
	pose["Rig:position"] = Vector3(0.0, 0.012, 0.0)
	pose["Rig/Pelvis/Torso/ArmBackShoulder:rotation"] = _rz(-0.28)
	pose["Rig/Pelvis/Torso/ArmFrontShoulder:rotation"] = _rz(0.28)
	return pose


func _neutral_animation() -> Animation:
	return _animation_from_poses(1.8, [0.0, 0.9, 1.8], [
		_pose({
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(0.13),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(-0.13),
		}),
		_pose({
			"Rig:position": Vector3(0.0, 0.015, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.025),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.02),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(0.16),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(-0.16),
		}),
		_pose({
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(0.13),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(-0.13),
		}),
	], true)


func _travel_animation() -> Animation:
	return _animation_from_poses(0.72, [0.0, 0.18, 0.36, 0.54, 0.72], [
		_travel_pose(1.0, 0.0),
		_travel_pose(0.0, 0.025),
		_travel_pose(-1.0, 0.0),
		_travel_pose(0.0, 0.025),
		_travel_pose(1.0, 0.0),
	], true)


func _travel_pose(direction: float, lift: float) -> Dictionary:
	return _pose({
		"Rig:position": Vector3(0.0, lift, 0.0),
		"Rig/Pelvis:rotation": _rz(-0.018 * direction),
		"Rig/Pelvis/Torso:rotation": _rz(-0.025),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.02),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.20 * direction),
		"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.16),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.20 * direction),
		"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.16),
		"Rig/Pelvis/LegBackHip:rotation": _rz(0.30 * direction),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.10 + 0.08 * maxf(direction, 0.0)),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.08),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(-0.30 * direction),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.10 + 0.08 * maxf(-direction, 0.0)),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.08),
	})


func _jump_animation() -> Animation:
	return _animation_from_poses(0.18, [0.0, 0.18], [
		_pose({
			"Rig:position": Vector3(0.0, -0.10, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.08),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.30),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(-0.18),
			"Rig/Pelvis/LegBackHip:rotation": _rz(0.16),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.50),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(-0.12),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.48),
		}),
		_pose({
			"Rig:position": Vector3(0.0, 0.02, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.03),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(0.52),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.30),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.28),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.20),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.48),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.10),
		}),
	], false)


func _airborne_animation() -> Animation:
	var pose := _pose({
		"Rig:position": Vector3(0.0, 0.035, 0.0),
		"Rig/Pelvis/Torso:rotation": _rz(-0.025),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.02),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.42),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.72),
		"Rig/Pelvis/LegBackHip:rotation": _rz(-0.40),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.62),
		"Rig/Pelvis/LegBackHip/LegBackKnee/FootBack:rotation": _rz(-0.14),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.14),
	})
	return _animation_from_poses(0.5, [0.0, 0.5], [pose, pose], true)


func _landing_animation() -> Animation:
	return _animation_from_poses(0.22, [0.0, 0.22], [
		_pose({
			"Rig:position": Vector3(0.0, -0.11, 0.0),
			"Rig/Pelvis/Torso:rotation": _rz(-0.08),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.20),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.28),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.48),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.52),
		}),
		_pose({
			"Rig/Pelvis/Torso:rotation": _rz(-0.025),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(0.12),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(-0.12),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.10),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.10),
		}),
	], false)


func _low_transition_animation() -> Animation:
	var pose := _pose({
		"Rig:position": Vector3(0.0, -0.27, 0.0),
		"Rig/Pelvis/Torso:rotation": _rz(-0.16),
		"Rig/Pelvis/Torso/Head:rotation": _rz(0.10),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.30),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.34),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.82),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.16),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.74),
	})
	return _animation_from_poses(0.55, [0.0, 0.55], [pose, pose], false)


func _balance_animation() -> Animation:
	return _animation_from_poses(1.3, [0.0, 0.65, 1.3], [
		_balance_pose(-0.025),
		_balance_pose(0.025),
		_balance_pose(-0.025),
	], true)


func _balance_pose(sway: float) -> Dictionary:
	return _pose({
		"Rig/Pelvis:rotation": _rz(sway),
		"Rig/Pelvis/Torso:rotation": _rz(-sway * 0.8),
		"Rig/Pelvis/Torso/Head:rotation": _rz(sway * 0.4),
		"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-1.02),
		"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(1.02),
		"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.05),
		"Rig/Pelvis/LegFrontHip:rotation": _rz(0.76),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(-1.28),
		"Rig/Pelvis/LegFrontHip/LegFrontKnee/FootFront:rotation": _rz(-0.18),
	})


func _stumble_animation() -> Animation:
	return _animation_from_poses(0.24, [0.0, 0.24], [
		_pose({
			"Rig/Pelvis/Torso:rotation": _rz(-0.10),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.10),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.22),
		}),
		_pose({
			"Rig:position": Vector3(0.04, -0.08, 0.0),
			"Rig/Pelvis:rotation": _rz(-0.16),
			"Rig/Pelvis/Torso:rotation": _rz(-0.40),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.16),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.92),
			"Rig/Pelvis/Torso/ArmBackShoulder/ArmBackElbow:rotation": _rz(0.34),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.66),
			"Rig/Pelvis/Torso/ArmFrontShoulder/ArmFrontElbow:rotation": _rz(0.28),
			"Rig/Pelvis/LegBackHip:rotation": _rz(-0.18),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.56),
			"Rig/Pelvis/LegFrontHip:rotation": _rz(0.30),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.30),
		}),
	], false)


func _recovery_animation() -> Animation:
	return _animation_from_poses(0.62, [0.0, 0.28, 0.62], [
		_pose({
			"Rig:position": Vector3(0.04, -0.08, 0.0),
			"Rig/Pelvis:rotation": _rz(-0.16),
			"Rig/Pelvis/Torso:rotation": _rz(-0.40),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.16),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.92),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.66),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.56),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.30),
		}),
		_pose({
			"Rig:position": Vector3(0.01, -0.025, 0.0),
			"Rig/Pelvis:rotation": _rz(-0.05),
			"Rig/Pelvis/Torso:rotation": _rz(-0.16),
			"Rig/Pelvis/Torso/Head:rotation": _rz(0.06),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(-0.30),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(0.30),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.24),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.18),
		}),
		_pose({
			"Rig/Pelvis/Torso:rotation": _rz(-0.025),
			"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rz(0.12),
			"Rig/Pelvis/Torso/ArmFrontShoulder:rotation": _rz(-0.12),
			"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rz(0.10),
			"Rig/Pelvis/LegFrontHip/LegFrontKnee:rotation": _rz(0.10),
		}),
	], false)


func _pose(overrides: Dictionary) -> Dictionary:
	var pose := {}
	for path in TRACK_PATHS:
		pose[path] = Vector3.ZERO
	for key in overrides:
		pose[key] = overrides[key]
	return pose


func _ry(angle: float) -> Vector3:
	return Vector3(0.0, angle, 0.0)


func _rz(angle: float) -> Vector3:
	return Vector3(0.0, 0.0, angle)


func _animation_from_poses(duration: float, times: Array, poses: Array, looped: bool) -> Animation:
	var animation := Animation.new()
	animation.length = duration
	if looped:
		animation.loop_mode = Animation.LOOP_LINEAR

	for path in TRACK_PATHS:
		var track := animation.add_track(Animation.TYPE_VALUE)
		animation.track_set_path(track, NodePath(path))
		animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR)
		for index in range(poses.size()):
			animation.track_insert_key(track, float(times[index]), poses[index][path])

	return animation
