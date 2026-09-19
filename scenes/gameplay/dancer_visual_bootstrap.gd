extends Node

const DANCER_VISUAL_SCRIPT := preload("res://scenes/gameplay/dancer_visual_motion_v5.gd")
const DANCER_TAP_FEEDBACK_SCRIPT := preload("res://scenes/gameplay/dancer_tap_feedback.gd")
const HUMANOID_LANDING_WINDOW := 0.22
const RUN_CONTACT_SAMPLE_COUNT := 32
const GAIT_SAMPLE_COUNT := 32

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
			_play_calibrated_walk(player)
		&"JUMP":
			_play_ballerina_animation(player, &"jump_start", false, 1.0)
		&"AIRBORNE":
			_play_ballerina_animation(player, &"jump_falling", true, 1.0)
		&"LANDING":
			# Start RUN on the foot that actually contacted the floor and LET THE
			# CYCLE CONTINUE. Freezing a contact pose while the CharacterBody
			# translates is exactly what produced the visible foot scraping.
			_begin_landing_run_contact(player)
		&"STUMBLE":
			_play_calibrated_run(player, 1.0)
		&"RECOVERY":
			_play_calibrated_run(player, 1.0)
		&"LOW_TRANSITION":
			_play_calibrated_run(player, 1.0)
		&"TRAVEL", &"BALANCE", &"MUSIC_FLOW", &"MUSIC_BUILD", &"MUSIC_RELEASE", &"MUSIC_PULSE", &"MUSIC_CLIMAX", &"MUSIC_PREP", &"MUSIC_ACCENT":
			_play_calibrated_run(player, 1.0)
		&"STAGE_READY", &"STAGE_BOW", &"STAGE_FINAL_BOW", &"STAGE_EXIT_TURN":
			# These are normally intercepted by handles_visual_state().
			_play_ballerina_animation(player, &"idle", true, 1.0)
		_:
			_play_ballerina_animation(player, &"idle", true, 1.0)


func _begin_landing_run_contact(player: AnimationPlayer) -> void:
	if not player.has_animation(&"run"):
		_play_ballerina_animation(player, &"idle", true, 1.0)
		return

	var skeleton := player.get_parent().get_node_or_null("Rig/Skeleton3D") as Skeleton3D
	if skeleton == null:
		_play_calibrated_walk(player)
		return

	var left_foot := _find_humanoid_bone(skeleton, ["leftfoot", "footl"])
	var right_foot := _find_humanoid_bone(skeleton, ["rightfoot", "footr"])
	if left_foot < 0 or right_foot < 0:
		_play_calibrated_walk(player)
		return

	# Determine the support foot from the falling pose before touching RUN.
	var left_y := skeleton.get_bone_global_pose(left_foot).origin.y
	var right_y := skeleton.get_bone_global_pose(right_foot).origin.y
	var landing_left := left_y <= right_y

	_cache_run_contact_phases(player, skeleton, left_foot, right_foot)
	var left_phase := float(player.get_meta("_run_left_contact_phase", 0.0))
	var right_phase := float(player.get_meta("_run_right_contact_phase", 0.0))
	var landing_phase := left_phase if landing_left else right_phase

	player.set_meta("_landing_support_left", landing_left)

	var desired_speed := _current_forward_speed(player, 4.0)
	var base_scale := _calibrated_gait_scale(
		player,
		&"run",
		desired_speed
	)

	# Contact begins at the calibrated support-foot speed. Absorption comes from
	# ankle/knee/hip articulation, not from slowing the clip under a translating
	# root. This keeps the planted foot approximately stationary in world X.
	player.speed_scale = base_scale
	var run_animation := player.get_animation(&"run")
	if run_animation != null:
		run_animation.loop_mode = Animation.LOOP_LINEAR
	player.play(&"run", 0.08)
	player.seek(
		clampf(
			landing_phase,
			0.0,
			maxf(run_animation.length - 0.001, 0.0)
		),
		true
	)


func _play_calibrated_run(
	player: AnimationPlayer,
	cadence_multiplier: float
) -> void:
	var desired_speed := _current_forward_speed(player, 4.0)
	var scale := (
		_calibrated_gait_scale(player, &"run", desired_speed)
		* cadence_multiplier
	)
	_play_ballerina_animation(player, &"run", true, scale)


func _play_calibrated_walk(player: AnimationPlayer) -> void:
	var desired_speed := _current_forward_speed(player, 1.55)
	var scale := _calibrated_gait_scale(
		player,
		&"walk",
		desired_speed
	)
	_play_ballerina_animation(player, &"walk", true, scale)


func _current_forward_speed(
	player: AnimationPlayer,
	fallback: float
) -> float:
	var dancer := _dancer_from_player(player)
	if dancer == null:
		return fallback

	var stage_speed := float(dancer.get("stage_entrance_speed"))
	if stage_speed > 0.05:
		return stage_speed

	var velocity: Vector3 = dancer.velocity
	if absf(velocity.x) > 0.05:
		return absf(velocity.x)

	var run_speed := float(dancer.get("run_speed"))
	if run_speed > 0.05:
		return run_speed
	return fallback


func _dancer_from_player(player: AnimationPlayer) -> CharacterBody3D:
	var node: Node = player
	while node != null:
		if node is CharacterBody3D:
			return node as CharacterBody3D
		node = node.get_parent()
	return null


func _calibrated_gait_scale(
	player: AnimationPlayer,
	animation_name: StringName,
	desired_world_speed: float
) -> float:
	var key := "_gait_backward_speed_%s" % String(animation_name)
	if not player.has_meta(key):
		player.set_meta(
			key,
			_measure_backward_support_speed(player, animation_name)
		)

	var backward_speed := float(player.get_meta(key, 0.0))
	if backward_speed <= 0.05:
		# The clip may not expose enough support translation for calibration.
		return 1.0

	return clampf(
		desired_world_speed / backward_speed,
		0.62,
		1.55
	)


func _measure_backward_support_speed(
	player: AnimationPlayer,
	animation_name: StringName
) -> float:
	if not player.has_animation(animation_name):
		return 0.0

	var skeleton := player.get_parent().get_node_or_null("Rig/Skeleton3D") as Skeleton3D
	if skeleton == null:
		return 0.0
	var left_foot := _find_humanoid_bone(skeleton, ["leftfoot", "footl"])
	var right_foot := _find_humanoid_bone(skeleton, ["rightfoot", "footr"])
	if left_foot < 0 or right_foot < 0:
		return 0.0

	var animation := player.get_animation(animation_name)
	if animation == null or animation.length <= 0.0001:
		return 0.0

	var previous_animation := StringName(player.current_animation)
	var previous_position := player.current_animation_position
	var previous_speed := player.speed_scale
	var was_playing := player.is_playing()

	var phases: Array[float] = []
	var left_positions: Array[Vector3] = []
	var right_positions: Array[Vector3] = []
	player.play(animation_name, 0.0)

	for sample_index in range(GAIT_SAMPLE_COUNT):
		var phase := (
			animation.length
			* float(sample_index)
			/ float(GAIT_SAMPLE_COUNT)
		)
		player.seek(phase, true)
		player.advance(0.0)
		phases.append(phase)
		left_positions.append(
			skeleton.global_transform
			* skeleton.get_bone_global_pose(left_foot).origin
		)
		right_positions.append(
			skeleton.global_transform
			* skeleton.get_bone_global_pose(right_foot).origin
		)

	var candidates: Array[float] = []
	var dt := animation.length / float(GAIT_SAMPLE_COUNT)
	for sample_index in range(GAIT_SAMPLE_COUNT):
		var previous_index := (
			sample_index - 1 + GAIT_SAMPLE_COUNT
		) % GAIT_SAMPLE_COUNT
		var next_index := (sample_index + 1) % GAIT_SAMPLE_COUNT
		var left_is_support := (
			left_positions[sample_index].y
			<= right_positions[sample_index].y
		)
		var positions := left_positions if left_is_support else right_positions
		var dx := positions[next_index].x - positions[previous_index].x

		# Correct the cyclic wrap so the derivative measures pose motion, not the
		# numerical phase discontinuity.
		if sample_index == 0 or sample_index == GAIT_SAMPLE_COUNT - 1:
			continue

		var vx := dx / (2.0 * dt)
		if vx < -0.05:
			candidates.append(-vx)

	_restore_sampled_animation(
		player,
		previous_animation,
		previous_position,
		previous_speed,
		was_playing
	)

	if candidates.is_empty():
		return 0.0

	candidates.sort()
	var middle := int(candidates.size() / 2)
	if candidates.size() % 2 == 1:
		return candidates[middle]
	return 0.5 * (
		candidates[middle - 1]
		+ candidates[middle]
	)


func _restore_sampled_animation(
	player: AnimationPlayer,
	previous_animation: StringName,
	previous_position: float,
	previous_speed: float,
	was_playing: bool
) -> void:
	player.speed_scale = previous_speed
	if (
		previous_animation != &""
		and player.has_animation(previous_animation)
	):
		player.play(previous_animation, 0.0)
		player.seek(previous_position, true)
		if not was_playing:
			player.pause()
	else:
		player.stop()


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

	var previous_animation := StringName(player.current_animation)
	var previous_position := player.current_animation_position
	var previous_speed := player.speed_scale
	var was_playing := player.is_playing()

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

		# True contact is the absolute LOWEST point of each foot's own cycle.
		# Relative left-vs-right height can falsely select the instant when the
		# opposite foot is merely very high, which caused the wrong stance phase.
		if left_y < left_best_score:
			left_best_score = left_y
			left_best_phase = phase
		if right_y < right_best_score:
			right_best_score = right_y
			right_best_phase = phase

	player.set_meta("_run_left_contact_phase", left_best_phase)
	player.set_meta("_run_right_contact_phase", right_best_phase)
	_restore_sampled_animation(
		player,
		previous_animation,
		previous_position,
		previous_speed,
		was_playing
	)


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
