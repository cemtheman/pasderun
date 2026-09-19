extends Node

const DANCER_VISUAL_SCRIPT := preload("res://scenes/gameplay/dancer_visual_motion_v5.gd")
const DANCER_TAP_FEEDBACK_SCRIPT := preload("res://scenes/gameplay/dancer_tap_feedback.gd")
const HUMANOID_LANDING_WINDOW := 0.22
const RUN_CONTACT_SAMPLE_COUNT := 32

func _ready() -> void:
	get_tree().node_added.connect(_on_node_added)
	call_deferred("_attach_existing_dancer")


func _on_node_added(node: Node) -> void:
	if node is CharacterBody3D and node.name == &"Dancer":
		call_deferred("_attach_visual", node)


func _attach_existing_dancer() -> void:
	var scene := get_tree().current_scene
	if scene == null:
		return
	var dancer := scene.get_node_or_null("Dancer")
	if dancer is CharacterBody3D:
		_attach_visual(dancer)


func _attach_visual(dancer: CharacterBody3D) -> void:
	if not is_instance_valid(dancer):
		return

	var visual := dancer.get_node_or_null("DancerVisual")
	if visual == null:
		visual = DANCER_VISUAL_SCRIPT.new()
		visual.name = "DancerVisual"
		dancer.add_child(visual)

	# Keep the accepted capsule visible unless the replacement visual actually
	# initialized its rig. A Phase 7 presentation failure must not make the
	# gameplay body disappear during development/runtime QA.
	if visual.get_node_or_null("Rig") == null:
		push_error("DancerVisual failed to initialize; keeping capsule fallback visible.")
		return

	# Prototype bridge: when an external rigged ballerina visual is already
	# parented under Dancer, keep the accepted Phase 7 visual/state machine
	# alive but hide its geometry. This lets the new skinned character inherit
	# gameplay motion without changing collision or dancer physics.
	var external_visual := dancer.get_node_or_null("BallerinaVisualV1")
	if external_visual is Node3D:
		visual.visible = false
		var external_player := external_visual.get_node_or_null("low_poly_girl/AnimationPlayer") as AnimationPlayer
		if external_player != null:
			_connect_ballerina_animation_bridge(visual, external_visual, external_player)
		else:
			push_warning("BallerinaVisualV1 found, but its AnimationPlayer is unavailable.")

	var capsule_visual := dancer.get_node_or_null("MeshInstance3D")
	if capsule_visual is GeometryInstance3D:
		capsule_visual.visible = false

	if dancer.get_node_or_null("TapVisualFeedback") == null:
		var tap_feedback := DANCER_TAP_FEEDBACK_SCRIPT.new()
		tap_feedback.name = "TapVisualFeedback"
		dancer.add_child(tap_feedback)



func _connect_ballerina_animation_bridge(
	visual: Node,
	external_visual: Node,
	player: AnimationPlayer
) -> void:
	if visual.get_meta("_ballerina_animation_bridge_connected", false):
		return

	visual.set_meta("_ballerina_animation_bridge_connected", true)
	visual.connect(
		"visual_state_changed",
		Callable(self, "_on_ballerina_visual_state_changed").bind(external_visual, player)
	)

	if visual.has_method("get_visual_state"):
		_on_ballerina_visual_state_changed(
			StringName(visual.call("get_visual_state")),
			external_visual,
			player
		)


func _on_ballerina_visual_state_changed(
	state: StringName,
	external_visual: Node,
	player: AnimationPlayer
) -> void:
	# Full-body retarget is now reserved for slow stage-presentation states.
	# Locomotion stays on the imported humanoid clips so spine/clavicle/wrist/toe
	# follow-through remains natural. Stumble/recovery are run clips with a late
	# procedural overlay applied by BallerinaVisualV1.
	if (
		external_visual != null
		and external_visual.has_method("handles_visual_state")
		and bool(external_visual.call("handles_visual_state", state))
	):
		player.stop()
		return

	match state:
		&"NEUTRAL":
			_play_ballerina_animation(player, &"idle", true, 1.0)
		&"STAGE_WALK":
			_play_ballerina_animation(player, &"walk", true, 1.0)
		&"JUMP":
			_play_ballerina_animation(player, &"jump_start", false, 1.0)
		&"AIRBORNE":
			_play_ballerina_animation(player, &"jump_falling", true, 1.0)
		&"LANDING":
			# Freeze the native RUN cycle on the actual landing-foot contact.
			# The landing overlay supplies plié/absorption without playing a
			# rebound clip. The next run-family state resumes on the OPPOSITE
			# contact, so the dancer steps through rather than hopping twice on
			# the foot that just landed.
			_hold_landing_contact(player)
		&"STUMBLE":
			_play_run_from_pending_contact(player, 0.94)
		&"RECOVERY":
			_play_run_from_pending_contact(player, 1.03)
		&"LOW_TRANSITION":
			_play_run_from_pending_contact(player, 0.92)
		&"TRAVEL", &"BALANCE", &"MUSIC_FLOW", &"MUSIC_BUILD", &"MUSIC_RELEASE", &"MUSIC_PULSE", &"MUSIC_CLIMAX", &"MUSIC_PREP", &"MUSIC_ACCENT":
			_play_run_from_pending_contact(player, 1.0)
		&"STAGE_READY", &"STAGE_BOW", &"STAGE_FINAL_BOW", &"STAGE_EXIT_TURN":
			# These are normally intercepted by handles_visual_state().
			_play_ballerina_animation(player, &"idle", true, 1.0)
		_:
			_play_ballerina_animation(player, &"idle", true, 1.0)


func _hold_landing_contact(player: AnimationPlayer) -> void:
	if not player.has_animation(&"run"):
		_play_ballerina_animation(player, &"idle", true, 1.0)
		return

	var skeleton := player.get_parent().get_node_or_null("Rig/Skeleton3D") as Skeleton3D
	if skeleton == null:
		_play_ballerina_animation(player, &"walk", true, 1.0)
		return

	var left_foot := _find_humanoid_bone(skeleton, ["leftfoot", "footl"])
	var right_foot := _find_humanoid_bone(skeleton, ["rightfoot", "footr"])
	if left_foot < 0 or right_foot < 0:
		_play_ballerina_animation(player, &"walk", true, 1.0)
		return

	# Read the support foot BEFORE changing the currently displayed falling pose.
	var left_y := skeleton.get_bone_global_pose(left_foot).origin.y
	var right_y := skeleton.get_bone_global_pose(right_foot).origin.y
	var landing_left := left_y <= right_y

	_cache_run_contact_phases(player, skeleton, left_foot, right_foot)
	var left_phase := float(player.get_meta("_run_left_contact_phase", 0.0))
	var right_phase := float(player.get_meta("_run_right_contact_phase", 0.0))
	var landing_phase := left_phase if landing_left else right_phase
	var next_phase := right_phase if landing_left else left_phase

	player.set_meta("_landing_support_left", landing_left)
	player.set_meta("_pending_run_contact_phase", next_phase)
	player.set_meta("_pending_run_contact_valid", true)

	# A contact pose, not an animation clip: no vertical rebound can occur here.
	player.speed_scale = 1.0
	player.play(&"run", 0.08)
	player.seek(landing_phase, true)
	player.pause()


func _play_run_from_pending_contact(
	player: AnimationPlayer,
	speed_scale: float
) -> void:
	var pending := bool(player.get_meta("_pending_run_contact_valid", false))
	if not pending:
		_play_ballerina_animation(player, &"run", true, speed_scale)
		return

	var run_animation := player.get_animation(&"run")
	if run_animation == null or run_animation.length <= 0.0001:
		player.set_meta("_pending_run_contact_valid", false)
		_play_ballerina_animation(player, &"run", true, speed_scale)
		return

	var phase := float(player.get_meta("_pending_run_contact_phase", 0.0))
	player.set_meta("_pending_run_contact_valid", false)
	player.speed_scale = speed_scale
	run_animation.loop_mode = Animation.LOOP_LINEAR
	player.play(&"run", 0.12)
	player.seek(
		clampf(phase, 0.0, maxf(run_animation.length - 0.001, 0.0)),
		true
	)


func _cache_run_contact_phases(
	player: AnimationPlayer,
	skeleton: Skeleton3D,
	left_foot: int,
	right_foot: int
) -> void:
	if (
		player.has_meta("_run_left_contact_phase")
		and player.has_meta("_run_right_contact_phase")
	):
		return

	var run_animation := player.get_animation(&"run")
	if run_animation == null or run_animation.length <= 0.0001:
		player.set_meta("_run_left_contact_phase", 0.0)
		player.set_meta("_run_right_contact_phase", 0.0)
		return

	var left_best_phase := 0.0
	var right_best_phase := run_animation.length * 0.5
	var left_best_score := INF
	var right_best_score := INF

	player.play(&"run", 0.0)
	for sample_index in range(RUN_CONTACT_SAMPLE_COUNT):
		var phase := (
			run_animation.length
			* float(sample_index)
			/ float(RUN_CONTACT_SAMPLE_COUNT)
		)
		player.seek(phase, true)
		player.advance(0.0)

		var left_y := skeleton.get_bone_global_pose(left_foot).origin.y
		var right_y := skeleton.get_bone_global_pose(right_foot).origin.y

		# Contact wants one foot distinctly lower than the other. The score uses
		# relative height, so pelvis bob/root height cannot bias phase selection.
		var left_score := left_y - right_y
		var right_score := right_y - left_y
		if left_score < left_best_score:
			left_best_score = left_score
			left_best_phase = phase
		if right_score < right_best_score:
			right_best_score = right_score
			right_best_phase = phase

	player.set_meta("_run_left_contact_phase", left_best_phase)
	player.set_meta("_run_right_contact_phase", right_best_phase)


func _find_humanoid_bone(
	skeleton: Skeleton3D,
	aliases: Array[String]
) -> int:
	var normalized_aliases: Array[String] = []
	for alias in aliases:
		normalized_aliases.append(_normalize_bone_name(alias))

	for bone_index in range(skeleton.get_bone_count()):
		var normalized_name := _normalize_bone_name(
			String(skeleton.get_bone_name(bone_index))
		)
		if normalized_name in normalized_aliases:
			return bone_index

	return -1


func _normalize_bone_name(value: String) -> String:
	return (
		value.to_lower()
		.replace("mixamorig", "")
		.replace(":", "")
		.replace("_", "")
		.replace(".", "")
		.replace("-", "")
		.replace(" ", "")
	)


func _play_ballerina_animation(
	player: AnimationPlayer,
	animation_name: StringName,
	looped: bool,
	speed_scale: float = 1.0
) -> void:
	if not player.has_animation(animation_name):
		push_warning(
			"Ballerina animation '%s' is unavailable; keeping the current animation."
			% String(animation_name)
		)
		return

	var animation := player.get_animation(animation_name)
	if animation != null:
		animation.loop_mode = Animation.LOOP_LINEAR if looped else Animation.LOOP_NONE

	player.speed_scale = speed_scale
	if player.current_animation == String(animation_name) and player.is_playing():
		return

	player.play(animation_name, 0.10)
