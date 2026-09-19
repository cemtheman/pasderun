extends Node3D

signal visual_state_changed(state: StringName)

# Phase 10.3 — single humanoid motion authority.
#
# Dancer owns gameplay/physics. This controller owns only the imported humanoid
# AnimationPlayer plus small anatomy-aware overlays. There is no mannequin
# source skeleton, semantic retarget layer, source root transfer or second
# visual state machine.
#
# Coordinate contract:
# +X = gameplay travel, +Y = up, +Z = audience/fourth wall.
# The imported girl's local +Z front is rotated by the scene wrapper onto +X.

const STATE_NEUTRAL := &"NEUTRAL"
const STATE_STAGE_WALK := &"STAGE_WALK"
const STATE_STAGE_BOW := &"STAGE_BOW"
const STATE_STAGE_READY := &"STAGE_READY"
const STATE_STAGE_FINAL_BOW := &"STAGE_FINAL_BOW"
const STATE_STAGE_EXIT_TURN := &"STAGE_EXIT_TURN"
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

const TAKEOFF_VISUAL_TIME := 0.20
const LANDING_VISUAL_TIME := 0.24
const STUMBLE_DURATION := 0.36
const RECOVERY_DURATION := 0.72
const STUMBLE_TORSO_PITCH := deg_to_rad(30.0)
const STAGE_BOW_DURATION := 1.65
const STAGE_BOW_TURN_IN := 0.28
const STAGE_BOW_TURN_OUT := 0.34
const STAGE_FINAL_BOW_DURATION := 2.60
const STAGE_FINAL_TURN_IN := 0.32
const STAGE_EXIT_TURN_DURATION := 0.38
const MUSIC_ACCENT_VISUAL_TIME := 0.18
const GAIT_SAMPLE_COUNT := 32
const RUN_CONTACT_SAMPLE_COUNT := 32
const TAP_FEEDBACK_SCRIPT := preload("res://scenes/gameplay/dancer_tap_feedback.gd")

@onready var _model_root: Node3D = $low_poly_girl
@onready var _skeleton: Skeleton3D = $low_poly_girl/Rig/Skeleton3D
@onready var _animation_player: AnimationPlayer = $low_poly_girl/AnimationPlayer

var _dancer: CharacterBody3D
var _model_base_transform: Transform3D
var _current_state: StringName = &""
var _stage_presentation_state: StringName = &""
var _state_elapsed := 0.0
var _was_on_floor := true
var _airborne_time := 0.0
var _landing_time := 0.0

var _music_expression_enabled := false
var _music_phrase_state: StringName = STATE_MUSIC_FLOW
var _music_preparing_action: StringName = &""
var _music_accent_remaining := 0.0

var _bones: Dictionary = {}
var _idle_global_poses: Dictionary = {}
var _stage_entry_globals: Dictionary = {}
var _trip_uses_left_foot := false
var _landing_support_left := false


func _ready() -> void:
	process_priority = 100
	_dancer = get_parent() as CharacterBody3D
	if _dancer == null:
		push_error("HumanoidMotionController must be a direct child of Dancer.")
		set_process(false)
		return
	if _skeleton == null or _animation_player == null or _model_root == null:
		push_error("HumanoidMotionController requires the imported humanoid rig and AnimationPlayer.")
		set_process(false)
		return

	_model_base_transform = _model_root.transform
	_resolve_humanoid_bones()
	_capture_idle_baseline()
	_attach_presentation_helpers()
	_was_on_floor = _dancer.is_on_floor()
	_set_visual_state(STATE_NEUTRAL, true)


func _process(delta: float) -> void:
	if _dancer == null:
		return

	_state_elapsed += delta
	_music_accent_remaining = maxf(_music_accent_remaining - delta, 0.0)
	var next_state := _resolve_visual_state(delta)
	if next_state != _current_state:
		_set_visual_state(next_state)

	_sync_native_gait_speed()
	_apply_visual_overlay(_current_state)


func set_stage_presentation_state(stage: StringName) -> void:
	var next_state := &""
	match stage:
		&"RUN":
			next_state = STATE_TRAVEL
		&"WALK":
			next_state = STATE_STAGE_WALK
		&"BOW":
			next_state = STATE_STAGE_BOW
		&"READY":
			next_state = STATE_STAGE_READY
		&"FINAL_BOW":
			next_state = STATE_STAGE_FINAL_BOW
		&"EXIT_TURN":
			next_state = STATE_STAGE_EXIT_TURN
		_:
			return

	if _stage_presentation_state == next_state:
		return
	_stage_presentation_state = next_state
	_set_visual_state(next_state, true)


func clear_stage_presentation() -> void:
	_stage_presentation_state = &""
	_model_root.transform = _model_base_transform
	_was_on_floor = _dancer.is_on_floor()
	_airborne_time = 0.0
	_landing_time = 0.0
	_set_visual_state(_resolve_visual_state(0.0), true)


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

	if _dancer.get("has_fallen") == true:
		return _current_state if _current_state != &"" else STATE_NEUTRAL

	# Contact has visual priority. A high drop may already have queued STUMBLE
	# in gameplay, but LANDING must be shown first.
	var grounded := _dancer.is_on_floor()
	if not grounded:
		if _was_on_floor:
			_airborne_time = 0.0
		_airborne_time += delta
		_landing_time = 0.0
		_was_on_floor = false
		if _dancer.velocity.y > 0.15 and _airborne_time <= TAKEOFF_VISUAL_TIME:
			return STATE_JUMP
		return STATE_AIRBORNE

	if not _was_on_floor:
		_landing_time = LANDING_VISUAL_TIME
		_airborne_time = 0.0
		_was_on_floor = true

	if _landing_time > 0.0:
		_landing_time = maxf(_landing_time - delta, 0.0)
		return STATE_LANDING

	var locomotion := &"NORMAL"
	if _dancer.has_method("get_locomotion_state"):
		locomotion = StringName(_dancer.call("get_locomotion_state"))

	if locomotion == STATE_STUMBLE:
		return STATE_STUMBLE
	if locomotion == STATE_RECOVERY:
		return STATE_RECOVERY
	if _dancer.get("in_low_transition") == true:
		return STATE_LOW_TRANSITION
	if _dancer.get("in_balance_zone") == true:
		return STATE_BALANCE

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

	if state in [STATE_STAGE_BOW, STATE_STAGE_FINAL_BOW, STATE_STAGE_READY, STATE_STAGE_EXIT_TURN]:
		_capture_stage_entry_pose()

	_current_state = state
	_state_elapsed = 0.0

	match state:
		STATE_NEUTRAL:
			_model_root.transform = _model_base_transform
			_play_native(&"idle", true, 1.0)
		STATE_STAGE_WALK:
			_model_root.transform = _model_base_transform
			_play_calibrated_gait(&"walk", 1.55)
		STATE_TRAVEL, STATE_BALANCE, STATE_LOW_TRANSITION, \
		STATE_MUSIC_FLOW, STATE_MUSIC_BUILD, STATE_MUSIC_RELEASE, \
		STATE_MUSIC_PULSE, STATE_MUSIC_CLIMAX, STATE_MUSIC_PREP, STATE_MUSIC_ACCENT:
			_model_root.transform = _model_base_transform
			_ensure_calibrated_run()
		STATE_JUMP:
			_model_root.transform = _model_base_transform
			_play_native(&"jump_start", false, 1.0)
		STATE_AIRBORNE:
			_model_root.transform = _model_base_transform
			_play_native(&"jump_falling", true, 1.0)
		STATE_LANDING:
			_model_root.transform = _model_base_transform
			_begin_landing_run_contact()
		STATE_STUMBLE:
			_model_root.transform = _model_base_transform
			_ensure_calibrated_run()
			_capture_trip_side_from_current_gait()
		STATE_RECOVERY:
			_model_root.transform = _model_base_transform
			_ensure_calibrated_run()
		STATE_STAGE_BOW, STATE_STAGE_READY, STATE_STAGE_FINAL_BOW, STATE_STAGE_EXIT_TURN:
			_animation_player.pause()

	visual_state_changed.emit(state)


func _apply_visual_overlay(state: StringName) -> void:
	match state:
		STATE_JUMP:
			_apply_jump_overlay()
		STATE_AIRBORNE:
			_apply_airborne_overlay()
		STATE_LANDING:
			_apply_landing_overlay()
		STATE_STUMBLE:
			_apply_stumble_overlay()
		STATE_RECOVERY:
			_apply_recovery_overlay()
		STATE_LOW_TRANSITION:
			_apply_low_transition_overlay()
		STATE_BALANCE:
			_apply_balance_overlay()
		STATE_STAGE_BOW:
			_apply_opening_reverence()
		STATE_STAGE_READY:
			_apply_stage_ready()
		STATE_STAGE_FINAL_BOW:
			_apply_final_reverence()
		STATE_STAGE_EXIT_TURN:
			_apply_stage_exit_turn()


func _attach_presentation_helpers() -> void:
	var capsule := _dancer.get_node_or_null("MeshInstance3D") as GeometryInstance3D
	if capsule != null:
		capsule.visible = false

	if _dancer.get_node_or_null("TapVisualFeedback") == null:
		var tap_feedback := TAP_FEEDBACK_SCRIPT.new()
		tap_feedback.name = "TapVisualFeedback"
		_dancer.add_child(tap_feedback)


func _play_native(
	animation_name: StringName,
	looped: bool,
	speed_scale: float
) -> void:
	if not _animation_player.has_animation(animation_name):
		push_warning("Humanoid animation '%s' is unavailable." % String(animation_name))
		return

	var animation := _animation_player.get_animation(animation_name)
	if animation != null:
		animation.loop_mode = Animation.LOOP_LINEAR if looped else Animation.LOOP_NONE

	_animation_player.speed_scale = speed_scale
	if (
		StringName(_animation_player.current_animation) == animation_name
		and _animation_player.is_playing()
	):
		return
	_animation_player.play(animation_name, 0.10)


func _ensure_calibrated_run() -> void:
	var desired_speed := _current_forward_speed(4.0)
	var scale := _calibrated_gait_scale(&"run", desired_speed)
	_play_native(&"run", true, scale)


func _play_calibrated_gait(animation_name: StringName, fallback_speed: float) -> void:
	var desired_speed := _current_forward_speed(fallback_speed)
	var scale := _calibrated_gait_scale(animation_name, desired_speed)
	_play_native(animation_name, true, scale)


func _sync_native_gait_speed() -> void:
	var current := StringName(_animation_player.current_animation)
	if current not in [&"run", &"walk"]:
		return

	var desired_speed := _current_forward_speed(4.0 if current == &"run" else 1.55)
	if desired_speed <= 0.05:
		return
	var key := "_humanoid_backward_speed_%s" % String(current)
	var backward_speed := float(_animation_player.get_meta(key, 0.0))
	if backward_speed <= 0.05:
		backward_speed = _measure_backward_support_speed(current)
		_animation_player.set_meta(key, backward_speed)
	if backward_speed <= 0.05:
		return

	_animation_player.speed_scale = clampf(
		desired_speed / backward_speed,
		0.62,
		1.55
	)


func _current_forward_speed(fallback: float) -> float:
	var stage_speed := float(_dancer.get("stage_entrance_speed"))
	if stage_speed > 0.05:
		return stage_speed
	if absf(_dancer.velocity.x) > 0.05:
		return absf(_dancer.velocity.x)
	var run_speed := float(_dancer.get("run_speed"))
	return run_speed if run_speed > 0.05 else fallback


func _calibrated_gait_scale(
	animation_name: StringName,
	desired_world_speed: float
) -> float:
	var key := "_humanoid_backward_speed_%s" % String(animation_name)
	if not _animation_player.has_meta(key):
		_animation_player.set_meta(
			key,
			_measure_backward_support_speed(animation_name)
		)
	var backward_speed := float(_animation_player.get_meta(key, 0.0))
	if backward_speed <= 0.05:
		return 1.0
	return clampf(desired_world_speed / backward_speed, 0.62, 1.55)


func _measure_backward_support_speed(animation_name: StringName) -> float:
	if not _animation_player.has_animation(animation_name):
		return 0.0

	var left_foot := _bone_index("left_foot")
	var right_foot := _bone_index("right_foot")
	if left_foot < 0 or right_foot < 0:
		return 0.0

	var animation := _animation_player.get_animation(animation_name)
	if animation == null or animation.length <= 0.0001:
		return 0.0

	var previous_animation := StringName(_animation_player.current_animation)
	var previous_position := _animation_player.current_animation_position
	var previous_speed := _animation_player.speed_scale
	var was_playing := _animation_player.is_playing()

	var left_positions: Array[Vector3] = []
	var right_positions: Array[Vector3] = []
	_animation_player.play(animation_name, 0.0)

	for sample_index in range(GAIT_SAMPLE_COUNT):
		var phase := animation.length * float(sample_index) / float(GAIT_SAMPLE_COUNT)
		_animation_player.seek(phase, true)
		_animation_player.advance(0.0)
		left_positions.append(_bone_world_position(left_foot))
		right_positions.append(_bone_world_position(right_foot))

	var candidates: Array[float] = []
	var dt := animation.length / float(GAIT_SAMPLE_COUNT)
	for sample_index in range(1, GAIT_SAMPLE_COUNT - 1):
		var left_support := (
			left_positions[sample_index].y <= right_positions[sample_index].y
		)
		var positions := left_positions if left_support else right_positions
		var vx := (
			positions[sample_index + 1].x
			- positions[sample_index - 1].x
		) / (2.0 * dt)
		if vx < -0.05:
			candidates.append(-vx)

	_restore_sampled_animation(
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
	return 0.5 * (candidates[middle - 1] + candidates[middle])


func _restore_sampled_animation(
	previous_animation: StringName,
	previous_position: float,
	previous_speed: float,
	was_playing: bool
) -> void:
	_animation_player.speed_scale = previous_speed
	if previous_animation != &"" and _animation_player.has_animation(previous_animation):
		_animation_player.play(previous_animation, 0.0)
		_animation_player.seek(previous_position, true)
		if not was_playing:
			_animation_player.pause()
	else:
		_animation_player.stop()


func _begin_landing_run_contact() -> void:
	if not _animation_player.has_animation(&"run"):
		_play_native(&"idle", true, 1.0)
		return

	var left_foot := _bone_index("left_foot")
	var right_foot := _bone_index("right_foot")
	if left_foot < 0 or right_foot < 0:
		_ensure_calibrated_run()
		return

	# Read the actual falling pose before switching to RUN.
	_landing_support_left = (
		_bone_world_position(left_foot).y <= _bone_world_position(right_foot).y
	)
	_cache_run_contact_phases()
	var phase_key := (
		"_humanoid_run_left_contact"
		if _landing_support_left
		else "_humanoid_run_right_contact"
	)
	var landing_phase := float(_animation_player.get_meta(phase_key, 0.0))
	var run_animation := _animation_player.get_animation(&"run")
	if run_animation == null:
		return

	run_animation.loop_mode = Animation.LOOP_LINEAR
	_animation_player.speed_scale = _calibrated_gait_scale(
		&"run",
		_current_forward_speed(4.0)
	)
	_animation_player.play(&"run", 0.08)
	_animation_player.seek(
		clampf(landing_phase, 0.0, maxf(run_animation.length - 0.001, 0.0)),
		true
	)


func _cache_run_contact_phases() -> void:
	if (
		_animation_player.has_meta("_humanoid_run_left_contact")
		and _animation_player.has_meta("_humanoid_run_right_contact")
	):
		return

	var left_foot := _bone_index("left_foot")
	var right_foot := _bone_index("right_foot")
	var run_animation := _animation_player.get_animation(&"run")
	if left_foot < 0 or right_foot < 0 or run_animation == null:
		return

	var previous_animation := StringName(_animation_player.current_animation)
	var previous_position := _animation_player.current_animation_position
	var previous_speed := _animation_player.speed_scale
	var was_playing := _animation_player.is_playing()

	var left_phase := 0.0
	var right_phase := run_animation.length * 0.5
	var left_low := INF
	var right_low := INF

	_animation_player.play(&"run", 0.0)
	for sample_index in range(RUN_CONTACT_SAMPLE_COUNT):
		var phase := (
			run_animation.length
			* float(sample_index)
			/ float(RUN_CONTACT_SAMPLE_COUNT)
		)
		_animation_player.seek(phase, true)
		_animation_player.advance(0.0)
		var left_y := _bone_world_position(left_foot).y
		var right_y := _bone_world_position(right_foot).y
		if left_y < left_low:
			left_low = left_y
			left_phase = phase
		if right_y < right_low:
			right_low = right_y
			right_phase = phase

	_animation_player.set_meta("_humanoid_run_left_contact", left_phase)
	_animation_player.set_meta("_humanoid_run_right_contact", right_phase)
	_restore_sampled_animation(
		previous_animation,
		previous_position,
		previous_speed,
		was_playing
	)


func _apply_jump_overlay() -> void:
	var phase := clampf(_state_elapsed / TAKEOFF_VISUAL_TIME, 0.0, 1.0)
	var strength := 0.22 * smoothstep(0.0, 1.0, phase)
	_apply_toe_line(strength)
	_apply_travel_arm_opening(0.18 * strength / 0.22)


func _apply_airborne_overlay() -> void:
	_apply_toe_line(0.26)
	var torso := _bone_index("chest")
	var head := _bone_index("head")
	_steer_segment_world_direction(
		torso,
		head,
		Vector3(0.02, 0.999, 0.0).normalized(),
		0.18
	)


func _apply_landing_overlay() -> void:
	var t := clampf(_state_elapsed / LANDING_VISUAL_TIME, 0.0, 1.0)
	var drop_distance := 0.0
	var was_jump := false
	if _dancer.has_method("get_last_landing_drop_distance"):
		drop_distance = float(_dancer.call("get_last_landing_drop_distance"))
	if _dancer.has_method("get_last_landing_was_jump"):
		was_jump = bool(_dancer.call("get_last_landing_was_jump"))

	var impact := 0.52 if was_jump else clampf(0.68 + drop_distance * 0.28, 0.68, 1.0)
	var compression := sin(PI * clampf(t / 0.92, 0.0, 1.0))
	var strength := 0.72 * impact * compression

	var hip := _bone_index("left_upper_leg" if _landing_support_left else "right_upper_leg")
	var knee := _bone_index("left_lower_leg" if _landing_support_left else "right_lower_leg")
	var foot := _bone_index("left_foot" if _landing_support_left else "right_foot")
	var side := _travel_pair_side_sign(_landing_support_left)

	# The run clip continues through contact; only the support chain absorbs.
	_steer_segment_world_direction(
		hip,
		knee,
		Vector3(0.28, -0.958, side * 0.04).normalized(),
		strength
	)
	_steer_segment_world_direction(
		knee,
		foot,
		Vector3(-0.18, -0.983, side * 0.02).normalized(),
		strength
	)
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(0.16 + 0.05 * impact, 0.985, 0.0).normalized(),
		0.42 * impact * compression
	)


func _capture_trip_side_from_current_gait() -> void:
	var left_foot := _bone_index("left_foot")
	var right_foot := _bone_index("right_foot")
	if left_foot < 0 or right_foot < 0:
		_trip_uses_left_foot = false
		return
	_trip_uses_left_foot = (
		_bone_world_position(left_foot).x > _bone_world_position(right_foot).x
	)


func _apply_stumble_overlay() -> void:
	var t := clampf(_state_elapsed / STUMBLE_DURATION, 0.0, 1.0)
	var peak := smoothstep(0.02, 0.70, t)
	var pitch_direction := Vector3(
		sin(STUMBLE_TORSO_PITCH),
		cos(STUMBLE_TORSO_PITCH),
		0.0
	).normalized()

	# Readable human loss of balance: torso reaches ~30 degrees forward while
	# the head counter-extends and the native run keeps translating underneath.
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		pitch_direction,
		0.92 * peak
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(-0.14, 0.990, 0.0).normalized(),
		0.72 * peak
	)

	var caught_hip := _bone_index(
		"left_upper_leg" if _trip_uses_left_foot else "right_upper_leg"
	)
	var caught_knee := _bone_index(
		"left_lower_leg" if _trip_uses_left_foot else "right_lower_leg"
	)
	var caught_foot := _bone_index(
		"left_foot" if _trip_uses_left_foot else "right_foot"
	)
	var caught_toe := _bone_index(
		"left_toe" if _trip_uses_left_foot else "right_toe"
	)
	var caught_side := _travel_pair_side_sign(_trip_uses_left_foot)
	var leg_strength := 0.78 * smoothstep(0.0, 0.48, t)
	_steer_segment_world_direction(
		caught_hip,
		caught_knee,
		Vector3(0.24, -0.969, caught_side * 0.05).normalized(),
		leg_strength
	)
	_steer_segment_world_direction(
		caught_knee,
		caught_foot,
		Vector3(0.05, -0.997, caught_side * 0.02).normalized(),
		leg_strength
	)
	_steer_segment_world_direction(
		caught_foot,
		caught_toe,
		Vector3(0.95, 0.30, caught_side * 0.05).normalized(),
		leg_strength * 0.84
	)

	var arm_strength := 0.70 * smoothstep(0.12, 0.74, t)
	var left_side := _travel_pair_side_sign(true)
	var right_side := -left_side
	_steer_segment_world_direction(
		_bone_index("left_upper_arm"),
		_bone_index("left_lower_arm"),
		Vector3(0.44, -0.36, left_side * 0.82).normalized(),
		arm_strength
	)
	_steer_segment_world_direction(
		_bone_index("right_upper_arm"),
		_bone_index("right_lower_arm"),
		Vector3(0.18, -0.58, right_side * 0.79).normalized(),
		arm_strength * 0.84
	)


func _apply_recovery_overlay() -> void:
	var t := clampf(_state_elapsed / RECOVERY_DURATION, 0.0, 1.0)
	var release := smoothstep(0.0, 1.0, t)
	var torso_strength := 0.68 * (1.0 - smoothstep(0.42, 0.94, t))
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(0.38, 0.925, 0.0).lerp(
			Vector3(0.04, 0.999, 0.0),
			release
		).normalized(),
		torso_strength
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(-0.08, 0.996, 0.0).normalized(),
		torso_strength * 0.70
	)

	# One emergency catch step comes from the leg opposite the caught foot.
	var catch_left := not _trip_uses_left_foot
	var catch_strength := 0.72 * sin(PI * clampf(t / 0.86, 0.0, 1.0))
	var side := _travel_pair_side_sign(catch_left)
	_steer_segment_world_direction(
		_bone_index("left_upper_leg" if catch_left else "right_upper_leg"),
		_bone_index("left_lower_leg" if catch_left else "right_lower_leg"),
		Vector3(0.44, -0.896, side * 0.05).normalized(),
		catch_strength
	)
	_steer_segment_world_direction(
		_bone_index("left_lower_leg" if catch_left else "right_lower_leg"),
		_bone_index("left_foot" if catch_left else "right_foot"),
		Vector3(0.24, -0.969, side * 0.03).normalized(),
		catch_strength
	)


func _apply_low_transition_overlay() -> void:
	var duration := maxf(float(_dancer.get("low_transition_duration")), 0.001)
	var remaining := clampf(float(_dancer.get("low_transition_timer")), 0.0, duration)
	var phase := 1.0 - remaining / duration
	var depth := sin(PI * clampf(phase, 0.0, 1.0))
	var strength := 0.58 * depth

	for left in [true, false]:
		var side := _travel_pair_side_sign(left)
		_steer_segment_world_direction(
			_bone_index("left_upper_leg" if left else "right_upper_leg"),
			_bone_index("left_lower_leg" if left else "right_lower_leg"),
			Vector3(0.24, -0.968, side * 0.05).normalized(),
			strength
		)
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(0.20, 0.980, 0.0).normalized(),
		0.46 * depth
	)


func _apply_balance_overlay() -> void:
	var displacement := clampf(_dancer.global_position.z / 1.25, -1.0, 1.0)
	var left_side := _travel_pair_side_sign(true)
	var right_side := -left_side
	_steer_segment_world_direction(
		_bone_index("left_upper_arm"),
		_bone_index("left_lower_arm"),
		Vector3(0.08, -0.20, left_side * 0.98).normalized(),
		0.42 + 0.12 * absf(displacement)
	)
	_steer_segment_world_direction(
		_bone_index("right_upper_arm"),
		_bone_index("right_lower_arm"),
		Vector3(0.08, -0.20, right_side * 0.98).normalized(),
		0.42 + 0.12 * absf(displacement)
	)


func _apply_opening_reverence() -> void:
	_apply_idle_baseline()

	var turn_in := smoothstep(
		0.0,
		1.0,
		clampf(_state_elapsed / STAGE_BOW_TURN_IN, 0.0, 1.0)
	)
	var turn_out_start := STAGE_BOW_DURATION - STAGE_BOW_TURN_OUT
	var turn_out := smoothstep(
		0.0,
		1.0,
		clampf(
			(_state_elapsed - turn_out_start) / STAGE_BOW_TURN_OUT,
			0.0,
			1.0
		)
	)
	var audience_alpha := turn_in * (1.0 - turn_out)
	_set_stage_orientation(audience_alpha)

	var bow_end := turn_out_start
	var phase := clampf(
		(_state_elapsed - STAGE_BOW_TURN_IN)
		/ maxf(bow_end - STAGE_BOW_TURN_IN, 0.001),
		0.0,
		1.0
	)
	_apply_reverence_anatomy(phase, false)
	_blend_stage_entry_pose(0.18)


func _apply_stage_ready() -> void:
	_apply_idle_baseline()
	_set_stage_orientation(0.0)
	_blend_stage_entry_pose(0.16)


func _apply_final_reverence() -> void:
	_apply_idle_baseline()
	var audience_alpha := smoothstep(
		0.0,
		1.0,
		clampf(_state_elapsed / STAGE_FINAL_TURN_IN, 0.0, 1.0)
	)
	_set_stage_orientation(audience_alpha)
	var phase := clampf(
		(_state_elapsed - STAGE_FINAL_TURN_IN)
		/ maxf(STAGE_FINAL_BOW_DURATION - STAGE_FINAL_TURN_IN, 0.001),
		0.0,
		1.0
	)
	_apply_reverence_anatomy(phase, true)
	_blend_stage_entry_pose(0.20)


func _apply_stage_exit_turn() -> void:
	_apply_idle_baseline()
	var t := smoothstep(
		0.0,
		1.0,
		clampf(_state_elapsed / STAGE_EXIT_TURN_DURATION, 0.0, 1.0)
	)
	_set_stage_orientation(1.0 - t)
	_blend_stage_entry_pose(0.16)


func _apply_reverence_anatomy(phase: float, final_reverence: bool) -> void:
	var p := smoothstep(0.0, 1.0, clampf(phase, 0.0, 1.0))
	var depth := sin(PI * p)
	var knee_angle := (0.64 if final_reverence else 0.46) * depth
	var c := cos(knee_angle)
	var s := sin(knee_angle)

	var left_leg_side := _audience_pair_side_sign(
		_bone_index("left_upper_leg"),
		_bone_index("right_upper_leg")
	)
	var right_leg_side := -left_leg_side
	var turnout := (0.15 if final_reverence else 0.11) * depth

	for left in [true, false]:
		var side := left_leg_side if left else right_leg_side
		var hip := _bone_index("left_upper_leg" if left else "right_upper_leg")
		var knee := _bone_index("left_lower_leg" if left else "right_lower_leg")
		var foot := _bone_index("left_foot" if left else "right_foot")
		# True demi-plié: knees advance toward audience +Z and shins fold back
		# toward planted feet. Side values are anatomical mirrors.
		_steer_segment_world_direction(
			hip,
			knee,
			Vector3(side * turnout, -c, s).normalized(),
			1.0
		)
		_steer_segment_world_direction(
			knee,
			foot,
			Vector3(-side * turnout * 0.55, -c, -s).normalized(),
			1.0
		)

	var leg_length := _idle_leg_length()
	var derived_drop := leg_length * (1.0 - cos(knee_angle))
	var max_drop := leg_length * (0.20 if final_reverence else 0.14)
	_model_root.position.y = (
		_model_base_transform.origin.y
		- minf(derived_drop, max_drop)
	)

	var left_arm_side := _audience_pair_side_sign(
		_bone_index("left_upper_arm"),
		_bone_index("right_upper_arm")
	)
	var right_arm_side := -left_arm_side
	var upper_out := lerpf(0.34, 0.88 if final_reverence else 0.82, depth)
	var upper_y := lerpf(-0.86, -0.18 if final_reverence else -0.24, depth)
	var upper_z := lerpf(0.35, 0.28, depth)
	var fore_in := lerpf(0.28, 0.58 if final_reverence else 0.52, depth)
	var fore_y := lerpf(-0.90, -0.20 if final_reverence else -0.28, depth)
	var fore_z := lerpf(0.30, 0.48 if final_reverence else 0.43, depth)

	# Port de bras is built from current shoulder->elbow->wrist geometry.
	# Upper arms open outward; FOREARMS REVERSE LATERALLY TOWARD CENTRE so the
	# silhouette closes into a rounded oval instead of continuing outward.
	for left in [true, false]:
		var side := left_arm_side if left else right_arm_side
		var shoulder := _bone_index("left_upper_arm" if left else "right_upper_arm")
		var elbow := _bone_index("left_lower_arm" if left else "right_lower_arm")
		var hand := _bone_index("left_hand" if left else "right_hand")
		_steer_segment_world_direction(
			shoulder,
			elbow,
			Vector3(side * upper_out, upper_y, upper_z).normalized(),
			1.0
		)
		_steer_segment_world_direction(
			elbow,
			hand,
			Vector3(-side * fore_in, fore_y, fore_z).normalized(),
			1.0
		)

	var torso_z := (0.10 if final_reverence else 0.055) * depth
	var head_z := (0.16 if final_reverence else 0.09) * depth
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(0.0, 0.997, torso_z).normalized(),
		0.82
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(0.0, 0.994, head_z).normalized(),
		0.74
	)


func _apply_toe_line(strength: float) -> void:
	for left in [true, false]:
		var foot := _bone_index("left_foot" if left else "right_foot")
		var toe := _bone_index("left_toe" if left else "right_toe")
		if foot < 0 or toe < 0:
			continue
		var side := _travel_pair_side_sign(left)
		_steer_segment_world_direction(
			foot,
			toe,
			Vector3(0.14, -0.985, side * 0.10).normalized(),
			strength
		)


func _apply_travel_arm_opening(strength: float) -> void:
	var left_side := _travel_pair_side_sign(true)
	var right_side := -left_side
	_steer_segment_world_direction(
		_bone_index("left_upper_arm"),
		_bone_index("left_lower_arm"),
		Vector3(0.12, -0.55, left_side * 0.83).normalized(),
		strength
	)
	_steer_segment_world_direction(
		_bone_index("right_upper_arm"),
		_bone_index("right_lower_arm"),
		Vector3(0.12, -0.55, right_side * 0.83).normalized(),
		strength
	)


func _set_stage_orientation(audience_alpha: float) -> void:
	var alpha := clampf(audience_alpha, 0.0, 1.0)
	var travel_basis := _model_base_transform.basis.orthonormalized()
	var audience_basis := (
		Basis(Vector3.UP, -PI * 0.5) * travel_basis
	).orthonormalized()
	var travel_q := travel_basis.get_rotation_quaternion()
	var audience_q := audience_basis.get_rotation_quaternion()
	_model_root.basis = Basis(travel_q.slerp(audience_q, alpha))


func _capture_idle_baseline() -> void:
	var previous_animation := StringName(_animation_player.current_animation)
	var previous_position := _animation_player.current_animation_position
	var previous_speed := _animation_player.speed_scale
	var was_playing := _animation_player.is_playing()

	if _animation_player.has_animation(&"idle"):
		_animation_player.play(&"idle", 0.0)
		_animation_player.seek(0.0, true)
		_animation_player.advance(0.0)

	_idle_global_poses.clear()
	for bone_idx in range(_skeleton.get_bone_count()):
		_idle_global_poses[bone_idx] = _skeleton.get_bone_global_pose(bone_idx)

	_restore_sampled_animation(
		previous_animation,
		previous_position,
		previous_speed,
		was_playing
	)


func _apply_idle_baseline() -> void:
	_model_root.transform = _model_base_transform
	for key in _idle_global_poses.keys():
		var bone_idx := int(key)
		_skeleton.set_bone_global_pose(
			bone_idx,
			_idle_global_poses[bone_idx]
		)


func _capture_stage_entry_pose() -> void:
	_stage_entry_globals.clear()
	for bone_idx in range(_skeleton.get_bone_count()):
		_stage_entry_globals[bone_idx] = _skeleton.get_bone_global_pose(bone_idx)


func _blend_stage_entry_pose(duration: float) -> void:
	if _stage_entry_globals.is_empty():
		return
	var alpha := smoothstep(
		0.0,
		1.0,
		clampf(_state_elapsed / maxf(duration, 0.001), 0.0, 1.0)
	)
	if alpha >= 0.999:
		return

	for key in _stage_entry_globals.keys():
		var bone_idx := int(key)
		var entry: Transform3D = _stage_entry_globals[bone_idx]
		var target := _skeleton.get_bone_global_pose(bone_idx)
		var blended_basis := Basis(
			entry.basis.get_rotation_quaternion().slerp(
				target.basis.get_rotation_quaternion(),
				alpha
			)
		)
		var blended_origin := entry.origin.lerp(target.origin, alpha)
		_skeleton.set_bone_global_pose(
			bone_idx,
			Transform3D(blended_basis, blended_origin)
		)


func _resolve_humanoid_bones() -> void:
	_bones = {
		"pelvis": _find_bone(["hips", "pelvis"]),
		"chest": _find_bone(["upperchest", "chest", "spine2", "spine02", "spine1", "spine01", "spine"]),
		"head": _find_bone(["head"]),
		"left_upper_arm": _find_bone(["leftupperarm", "upperarml", "leftarm", "arml"]),
		"left_lower_arm": _find_bone(["leftlowerarm", "lowerarml", "leftforearm", "forearml"]),
		"left_hand": _find_bone(["lefthand", "handl"]),
		"right_upper_arm": _find_bone(["rightupperarm", "upperarmr", "rightarm", "armr"]),
		"right_lower_arm": _find_bone(["rightlowerarm", "lowerarmr", "rightforearm", "forearmr"]),
		"right_hand": _find_bone(["righthand", "handr"]),
		"left_upper_leg": _find_bone(["leftupperleg", "upperlegl", "leftupleg", "leftthigh", "thighl"]),
		"left_lower_leg": _find_bone(["leftlowerleg", "lowerlegl", "leftleg", "leftcalf", "calfl", "leftshin", "shinl"]),
		"left_foot": _find_bone(["leftfoot", "footl"]),
		"left_toe": _find_bone(["lefttoebase", "lefttoe", "toel"]),
		"right_upper_leg": _find_bone(["rightupperleg", "upperlegr", "rightupleg", "rightthigh", "thighr"]),
		"right_lower_leg": _find_bone(["rightlowerleg", "lowerlegr", "rightleg", "rightcalf", "calfr", "rightshin", "shinr"]),
		"right_foot": _find_bone(["rightfoot", "footr"]),
		"right_toe": _find_bone(["righttoebase", "righttoe", "toer"]),
	}


func _find_bone(aliases: Array[String]) -> int:
	var normalized_aliases: Array[String] = []
	for alias in aliases:
		normalized_aliases.append(_normalize_bone_name(alias))

	for bone_idx in range(_skeleton.get_bone_count()):
		var normalized := _normalize_bone_name(
			String(_skeleton.get_bone_name(bone_idx))
		)
		if normalized in normalized_aliases:
			return bone_idx
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


func _bone_index(label: String) -> int:
	return int(_bones.get(label, -1))


func _bone_world_position(bone_idx: int) -> Vector3:
	if bone_idx < 0:
		return _skeleton.global_position
	return (
		_skeleton.global_transform
		* _skeleton.get_bone_global_pose(bone_idx).origin
	)


func _travel_pair_side_sign(left: bool) -> float:
	var left_idx := _bone_index("left_upper_leg")
	var right_idx := _bone_index("right_upper_leg")
	if left_idx < 0 or right_idx < 0:
		return 1.0 if left else -1.0
	var left_z := _bone_world_position(left_idx).z
	var right_z := _bone_world_position(right_idx).z
	var left_sign := -1.0 if left_z < right_z else 1.0
	return left_sign if left else -left_sign


func _audience_pair_side_sign(left_idx: int, right_idx: int) -> float:
	if left_idx < 0 or right_idx < 0:
		return -1.0
	var left_x := _bone_world_position(left_idx).x
	var right_x := _bone_world_position(right_idx).x
	return -1.0 if left_x < right_x else 1.0


func _idle_leg_length() -> float:
	var lengths: Array[float] = []
	for left in [true, false]:
		var hip := _bone_index("left_upper_leg" if left else "right_upper_leg")
		var knee := _bone_index("left_lower_leg" if left else "right_lower_leg")
		var foot := _bone_index("left_foot" if left else "right_foot")
		if (
			hip < 0
			or knee < 0
			or foot < 0
			or not _idle_global_poses.has(hip)
			or not _idle_global_poses.has(knee)
			or not _idle_global_poses.has(foot)
		):
			continue
		var hip_pose: Transform3D = _idle_global_poses[hip]
		var knee_pose: Transform3D = _idle_global_poses[knee]
		var foot_pose: Transform3D = _idle_global_poses[foot]
		lengths.append(
			(knee_pose.origin - hip_pose.origin).length()
			+ (foot_pose.origin - knee_pose.origin).length()
		)
	if lengths.is_empty():
		return 0.90
	var total := 0.0
	for value in lengths:
		total += value
	return total / float(lengths.size())


func _steer_segment_world_direction(
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
	var segment := child_current.origin - parent_current.origin
	if segment.length_squared() <= 0.000001:
		return

	var skeleton_world := _skeleton.global_transform.basis.orthonormalized()
	var current_direction_world := (
		skeleton_world * segment.normalized()
	).normalized()
	var desired := desired_world_direction.normalized()
	if current_direction_world.dot(desired) < -0.9999:
		desired = (desired + Vector3(0.0, 0.0001, 0.0001)).normalized()

	# No local-axis guessing: align the CURRENT anatomical segment in world
	# space, then blend the resulting quaternion back into skeleton space.
	var align_world := Basis(Quaternion(current_direction_world, desired))
	var current_world_basis := (
		skeleton_world * parent_current.basis
	).orthonormalized()
	var steered_world_basis := (
		align_world * current_world_basis
	).orthonormalized()
	var steered_skeleton_basis := (
		skeleton_world.inverse() * steered_world_basis
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
