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
const OPENING_REVERENCE := &"OPENING_REVERENCE"
const FINAL_REVERENCE := &"FINAL_REVERENCE"
const STUMBLE_TORSO_PITCH := deg_to_rad(32.0)
const STAGE_BOW_DURATION := 2.25
const STAGE_BOW_TURN_IN := 0.32
const STAGE_BOW_TURN_OUT := 0.30
const STAGE_FINAL_BOW_DURATION := 2.85
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
		_dancer.call_deferred("add_child", tap_feedback)

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
	var foot_catch := smoothstep(0.0, 0.24, t)
	var fall := smoothstep(0.08, 0.74, t)
	var counter_reaction := smoothstep(0.14, 0.82, t)

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
	var pitch_direction := Vector3(
		sin(STUMBLE_TORSO_PITCH),
		cos(STUMBLE_TORSO_PITCH),
		caught_side * 0.055
	).normalized()

	# The caught foot loses swing freedom first; momentum then carries the centre
	# forward. The native RUN clip remains active underneath this visual overlay.
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		pitch_direction,
		fall
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(-0.20, 0.978, -caught_side * 0.05).normalized(),
		0.86 * counter_reaction
	)

	var leg_strength := 0.94 * foot_catch
	_steer_segment_world_direction(
		caught_hip,
		caught_knee,
		Vector3(0.18, -0.982, caught_side * 0.04).normalized(),
		leg_strength
	)
	_steer_segment_world_direction(
		caught_knee,
		caught_foot,
		Vector3(-0.02, -0.998, caught_side * 0.02).normalized(),
		leg_strength
	)
	_steer_segment_world_direction(
		caught_foot,
		caught_toe,
		Vector3(0.84, -0.16, caught_side * 0.05).normalized(),
		0.88 * leg_strength
	)

	# Arms react after the foot catch, and deliberately do not mirror one another.
	# They remain curved balance tools rather than turning into a flailing T-pose.
	var arm_strength := 0.86 * smoothstep(0.16, 0.78, t)
	for left in [true, false]:
		var same_side_as_catch: bool = left == _trip_uses_left_foot
		var side := _travel_pair_side_sign(left)
		var shoulder := _bone_index("left_upper_arm" if left else "right_upper_arm")
		var elbow := _bone_index("left_lower_arm" if left else "right_lower_arm")
		var hand := _bone_index("left_hand" if left else "right_hand")
		var upper_direction := Vector3(
			-0.10 if same_side_as_catch else 0.36,
			-0.28 if same_side_as_catch else -0.08,
			side * (0.95 if same_side_as_catch else 0.91)
		).normalized()
		var fore_direction := Vector3(
			0.12 if same_side_as_catch else -0.04,
			-0.62 if same_side_as_catch else -0.44,
			-side * (0.66 if same_side_as_catch else 0.78)
		).normalized()
		_steer_segment_world_direction(
			shoulder,
			elbow,
			upper_direction,
			arm_strength
		)
		_steer_segment_world_direction(
			elbow,
			hand,
			fore_direction,
			0.76 * arm_strength
		)



func _apply_recovery_overlay() -> void:
	var t := clampf(_state_elapsed / RECOVERY_DURATION, 0.0, 1.0)
	var release := smoothstep(0.0, 1.0, t)
	var torso_strength := 0.88 * (1.0 - smoothstep(0.54, 0.98, t))
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(0.48, 0.877, 0.0).lerp(
			Vector3(0.04, 0.999, 0.0),
			release
		).normalized(),
		torso_strength
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(-0.14, 0.990, 0.0).lerp(
			Vector3(0.0, 1.0, 0.0),
			smoothstep(0.24, 0.96, t)
		).normalized(),
		0.78 * torso_strength
	)

	# The opposite/free leg solves the fall with one clearly advanced catch step.
	# Native RUN remains live underneath: no pause, seek or phase teleport.
	var catch_left := not _trip_uses_left_foot
	var side := _travel_pair_side_sign(catch_left)
	var catch_hip := _bone_index(
		"left_upper_leg" if catch_left else "right_upper_leg"
	)
	var catch_knee := _bone_index(
		"left_lower_leg" if catch_left else "right_lower_leg"
	)
	var catch_foot := _bone_index(
		"left_foot" if catch_left else "right_foot"
	)
	var other_foot := _bone_index(
		"right_foot" if catch_left else "left_foot"
	)
	var pelvis := _bone_index("pelvis")
	var leg_length := _idle_leg_length()
	var catch_advance := (
		smoothstep(0.0, 0.20, t)
		* (1.0 - smoothstep(0.72, 0.94, t))
	)
	var support_accept := (
		smoothstep(0.26, 0.50, t)
		* (1.0 - smoothstep(0.84, 1.0, t))
	)
	var catch_strength := clampf(
		1.00 * catch_advance + 0.82 * support_accept,
		0.0,
		1.0
	)
	var accept_alpha := smoothstep(0.34, 0.66, t)

	var pelvis_position := _bone_world_position(pelvis)
	var catch_hip_position := _bone_world_position(catch_hip)
	var catch_foot_position := _bone_world_position(catch_foot)
	var other_foot_position := _bone_world_position(other_foot)
	var floor_y := minf(catch_foot_position.y, other_foot_position.y)
	var catch_forward := lerpf(0.64, 0.30, accept_alpha) * leg_length
	var catch_foot_target := Vector3(
		pelvis_position.x + catch_forward,
		floor_y,
		pelvis_position.z + side * 0.045 * leg_length
	)
	var catch_knee_target := catch_hip_position.lerp(catch_foot_target, 0.52)
	catch_knee_target += Vector3(
		0.08 * leg_length,
		0.14 * leg_length,
		side * 0.015 * leg_length
	)

	_steer_segment_toward_world_point(
		catch_hip,
		catch_knee,
		catch_knee_target,
		catch_strength
	)
	_steer_segment_toward_world_point(
		catch_knee,
		catch_foot,
		catch_foot_target,
		catch_strength
	)

	# Balance-correction arms resolve after support acceptance rather than
	# vanishing on the first recovery frame.
	var arm_recovery_strength := 0.66 * (1.0 - smoothstep(0.42, 0.98, t))
	for left in [true, false]:
		var same_side_as_catch: bool = left == _trip_uses_left_foot
		var arm_side := _travel_pair_side_sign(left)
		_steer_segment_world_direction(
			_bone_index("left_upper_arm" if left else "right_upper_arm"),
			_bone_index("left_lower_arm" if left else "right_lower_arm"),
			Vector3(
				-0.04 if same_side_as_catch else 0.24,
				-0.38 if same_side_as_catch else -0.18,
				arm_side * 0.92
			).normalized(),
			arm_recovery_strength
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
	var profile := _reverence_profile(OPENING_REVERENCE)

	var turn_in := smoothstep(
		0.0,
		1.0,
		clampf(_state_elapsed / STAGE_BOW_TURN_IN, 0.0, 1.0)
	)
	var turn_out_start := float(profile["rise_end"])
	var turn_out := smoothstep(
		0.0,
		1.0,
		clampf(
			(_state_elapsed - turn_out_start) / STAGE_BOW_TURN_OUT,
			0.0,
			1.0
		)
	)
	_set_stage_orientation(turn_in * (1.0 - turn_out))
	_apply_opening_reverence_phrase_v1(_state_elapsed)
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
	_apply_reverence_phrase(_state_elapsed, FINAL_REVERENCE)
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



func _reverence_profile(variant: StringName) -> Dictionary:
	if variant == FINAL_REVERENCE:
		return {
			"duration": STAGE_FINAL_BOW_DURATION,
			"place_end": 0.60,
			"plie_end": 1.55,
			"rise_end": 2.35,
			"settle_end": 2.85,
			"plie_angle": 0.62,
			"turnout": 0.15,
			"root_drop_ratio": 0.18,
			"working_cross": 0.070,
			"weight_shift": 0.034,
			"torso_ack": 0.075,
			"head_ack": 0.135,
			"support_left": false,
			"expressive_left": false,
		}
	return {
		"duration": STAGE_BOW_DURATION,
		"place_end": 0.55,
		"plie_end": 1.35,
		"rise_end": 1.95,
		"settle_end": 2.25,
		"plie_angle": 0.50,
		"turnout": 0.12,
		"root_drop_ratio": 0.14,
		"working_cross": 0.050,
		"weight_shift": 0.024,
		"torso_ack": 0.050,
		"head_ack": 0.095,
		"support_left": true,
		"expressive_left": true,
	}



func _apply_opening_reverence_phrase_v1(elapsed: float) -> void:
	var profile := _reverence_profile(OPENING_REVERENCE)
	var duration := float(profile["duration"])
	var u := clampf(elapsed / maxf(duration, 0.001), 0.0, 1.0)

	# Révérence Motion Contract v1:
	# placement -> arm gather/en-avant passage -> knees soften -> pelvis follows
	# -> torso acknowledges -> head follows -> legs rise -> torso/head recover
	# -> arms resolve. The overlaps are intentional; nothing starts all at once.
	var placement := smoothstep(0.00, 0.18, u)
	var arm_enavant := smoothstep(0.08, 0.30, u)
	var arm_open := smoothstep(0.34, 0.64, u)
	var leg_descent := smoothstep(0.42, 0.68, u)
	var leg_rise := smoothstep(0.70, 0.88, u)
	var leg_depth := leg_descent * (1.0 - leg_rise)
	var pelvis_descent := smoothstep(0.46, 0.70, u)
	var pelvis_rise := smoothstep(0.72, 0.90, u)
	var pelvis_depth := pelvis_descent * (1.0 - pelvis_rise)
	var torso_in := smoothstep(0.52, 0.72, u)
	var torso_out := smoothstep(0.76, 0.92, u)
	var torso_ack := torso_in * (1.0 - torso_out)
	var head_in := smoothstep(0.58, 0.76, u)
	var head_out := smoothstep(0.82, 0.96, u)
	var head_ack := head_in * (1.0 - head_out)
	var arm_resolve := smoothstep(0.78, 1.00, u)
	var wrist_follow := (
		smoothstep(0.18, 0.54, u)
		* (1.0 - smoothstep(0.84, 1.00, u))
	)
	var settle := smoothstep(0.84, 1.00, u)

	_apply_reverence_leg_chain(profile, placement, leg_depth, settle)
	_apply_opening_pelvis_follow(profile, pelvis_depth)
	_apply_opening_clavicle_phrase(
		profile,
		arm_enavant,
		arm_open,
		arm_resolve
	)
	_apply_opening_port_de_bras_curve(
		profile,
		arm_enavant,
		arm_open,
		arm_resolve,
		wrist_follow
	)
	_apply_opening_epaulement_phrase(profile, torso_ack, head_ack)


func _apply_opening_pelvis_follow(
	profile: Dictionary,
	pelvis_depth: float
) -> void:
	var leg_length := _idle_leg_length()
	var knee_angle := float(profile["plie_angle"]) * pelvis_depth
	var derived_drop := leg_length * (1.0 - cos(knee_angle))
	var max_drop := leg_length * float(profile["root_drop_ratio"])
	_model_root.position.y = (
		_model_base_transform.origin.y
		- minf(derived_drop, max_drop)
	)


func _apply_opening_clavicle_phrase(
	profile: Dictionary,
	arm_enavant: float,
	arm_open: float,
	arm_resolve: float
) -> void:
	var support := (
		maxf(arm_enavant * 0.72, arm_open)
		* (1.0 - arm_resolve)
	)
	if support <= 0.001:
		return

	var chest := _bone_index("chest")
	var chest_position := _bone_world_position(chest)
	for left in [true, false]:
		var clavicle := _bone_index("left_clavicle" if left else "right_clavicle")
		var shoulder := _bone_index("left_upper_arm" if left else "right_upper_arm")
		if clavicle < 0 or shoulder < 0:
			continue

		var clavicle_position := _bone_world_position(clavicle)
		var shoulder_position := _bone_world_position(shoulder)
		var clavicle_length := maxf(
			clavicle_position.distance_to(shoulder_position),
			0.001
		)
		var outward := shoulder_position - chest_position
		outward -= Vector3.UP * outward.dot(Vector3.UP)
		if outward.length_squared() <= 0.000001:
			outward = Vector3(-1.0 if left else 1.0, 0.0, 0.0)
		outward = outward.normalized()

		# Clavicle follows arm elevation; it carries rather than shrugs.
		var lift := 0.025 + 0.035 * support
		var target_direction := (
			outward
			+ Vector3.UP * lift
			+ Vector3(0.0, 0.0, 0.06)
		).normalized()
		var shoulder_target := (
			clavicle_position
			+ target_direction * clavicle_length
		)
		_steer_segment_toward_world_point(
			clavicle,
			shoulder,
			shoulder_target,
			0.12 * support
		)


func _apply_opening_port_de_bras_curve(
	profile: Dictionary,
	arm_enavant: float,
	arm_open: float,
	arm_resolve: float,
	wrist_follow: float
) -> void:
	var left_shoulder := _bone_index("left_upper_arm")
	var right_shoulder := _bone_index("right_upper_arm")
	var chest := _bone_index("chest")
	var chest_position := _bone_world_position(chest)
	var shoulder_center := chest_position
	if left_shoulder >= 0 and right_shoulder >= 0:
		shoulder_center = (
			_bone_world_position(left_shoulder)
			+ _bone_world_position(right_shoulder)
		) * 0.5

	var audience_forward := Vector3(0.0, 0.0, 1.0)
	for left in [true, false]:
		var shoulder := left_shoulder if left else right_shoulder
		var elbow := _bone_index("left_lower_arm" if left else "right_lower_arm")
		var hand := _bone_index("left_hand" if left else "right_hand")
		var middle := _bone_index("left_middle" if left else "right_middle")
		if shoulder < 0 or elbow < 0:
			continue

		var shoulder_position := _bone_world_position(shoulder)
		var elbow_position := _bone_world_position(elbow)
		var outward := shoulder_position - shoulder_center
		outward -= Vector3.UP * outward.dot(Vector3.UP)
		if outward.length_squared() <= 0.000001:
			outward = Vector3(-1.0 if left else 1.0, 0.0, 0.0)
		outward = outward.normalized()

		var upper_length := maxf(
			shoulder_position.distance_to(elbow_position),
			0.001
		)
		var forearm_length := upper_length * 0.92
		if hand >= 0:
			forearm_length = maxf(
				elbow_position.distance_to(_bone_world_position(hand)),
				0.001
			)
		var reach := upper_length + forearm_length

		# LOW -> EN-AVANT -> OPEN are successive landmarks on one continuous
		# curve. The arms visibly travel before and during the plié instead of
		# holding one waist-level shape.
		var low_elbow := (
			shoulder_position
			+ outward * upper_length * 0.32
			- Vector3.UP * upper_length * 0.48
			+ audience_forward * upper_length * 0.12
		)
		var low_hand := (
			shoulder_center
			+ outward * reach * 0.10
			- Vector3.UP * reach * 0.56
			+ audience_forward * reach * 0.22
		)
		var enavant_elbow := (
			shoulder_position
			+ outward * upper_length * 0.50
			- Vector3.UP * upper_length * 0.18
			+ audience_forward * upper_length * 0.18
		)
		var enavant_hand := (
			shoulder_center
			+ outward * reach * 0.05
			- Vector3.UP * reach * 0.28
			+ audience_forward * reach * 0.34
		)
		var open_elbow := (
			shoulder_position
			+ outward * upper_length * 0.82
			- Vector3.UP * upper_length * 0.10
			+ audience_forward * upper_length * 0.14
		)
		var open_hand := (
			shoulder_center
			+ outward * reach * 0.68
			- Vector3.UP * reach * 0.18
			+ audience_forward * reach * 0.24
		)
		var resolve_elbow := (
			shoulder_position
			+ outward * upper_length * 0.34
			- Vector3.UP * upper_length * 0.46
			+ audience_forward * upper_length * 0.12
		)
		var resolve_hand := (
			shoulder_center
			+ outward * reach * 0.10
			- Vector3.UP * reach * 0.52
			+ audience_forward * reach * 0.20
		)

		var elbow_target := low_elbow.lerp(enavant_elbow, arm_enavant)
		var hand_target := low_hand.lerp(enavant_hand, arm_enavant)
		elbow_target = elbow_target.lerp(open_elbow, arm_open)
		hand_target = hand_target.lerp(open_hand, arm_open)
		elbow_target = elbow_target.lerp(resolve_elbow, arm_resolve)
		hand_target = hand_target.lerp(resolve_hand, arm_resolve)

		_steer_segment_toward_world_point(
			shoulder,
			elbow,
			elbow_target,
			0.97
		)
		if hand >= 0:
			_steer_segment_toward_world_point(
				elbow,
				hand,
				hand_target,
				0.97
			)
			if middle >= 0:
				# The hand continues the forearm curve. It no longer receives an
				# independent wrist angle that can break the port-de-bras line.
				var forearm_tangent := (hand_target - elbow_target).normalized()
				var hand_position := _bone_world_position(hand)
				var middle_position := _bone_world_position(middle)
				var hand_axis_length := maxf(
					hand_position.distance_to(middle_position),
					0.001
				)
				var hand_finish_target := (
					hand_position
					+ forearm_tangent * hand_axis_length
				)
				_steer_segment_toward_world_point(
					hand,
					middle,
					hand_finish_target,
					0.18 + 0.30 * wrist_follow
				)


func _apply_opening_epaulement_phrase(
	profile: Dictionary,
	torso_ack: float,
	head_ack: float
) -> void:
	var expressive_left := bool(profile["expressive_left"])
	var expressive_side := _audience_pair_side_sign(
		_bone_index("left_upper_arm"),
		_bone_index("right_upper_arm")
	)
	if not expressive_left:
		expressive_side = -expressive_side

	# The torso joins after the legs/pelvis; the head joins after the torso.
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(
			expressive_side * 0.010 * torso_ack,
			0.999,
			float(profile["torso_ack"]) * torso_ack
		).normalized(),
		0.78
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(
			expressive_side * 0.040 * head_ack,
			0.996,
			float(profile["head_ack"]) * head_ack
		).normalized(),
		0.74
	)


func _apply_reverence_phrase(elapsed: float, variant: StringName) -> void:
	# Final révérence keeps the accepted Phase 10.3.2 phrase path.
	var profile := _reverence_profile(variant)
	var place_end := float(profile["place_end"])
	var plie_end := float(profile["plie_end"])
	var rise_end := float(profile["rise_end"])
	var settle_end := float(profile["settle_end"])

	# ARRIVE/PLACE -> DEMI-PLIÉ -> RISE -> SETTLE is one continuous phrase.
	# Lower body, arms, torso and head deliberately use offset timing windows.
	var placement := smoothstep(0.04, place_end, elapsed)
	var descent := smoothstep(place_end, plie_end, elapsed)
	var rise := smoothstep(plie_end, rise_end, elapsed)
	var depth := descent * (1.0 - rise)
	var settle := smoothstep(rise_end, settle_end, elapsed)

	_apply_reverence_leg_chain(profile, placement, depth, settle)
	_apply_reverence_clavicle_support(profile, elapsed, variant)
	_apply_reverence_port_de_bras(profile, elapsed, variant)
	_apply_reverence_epaulement(profile, elapsed)



func _apply_reverence_leg_chain(
	profile: Dictionary,
	placement: float,
	depth: float,
	settle: float
) -> void:
	var support_left := bool(profile["support_left"])
	var left_leg_side := _audience_pair_side_sign(
		_bone_index("left_upper_leg"),
		_bone_index("right_upper_leg")
	)
	var right_leg_side := -left_leg_side
	var support_side := left_leg_side if support_left else right_leg_side
	var turnout := float(profile["turnout"])
	var working_cross := float(profile["working_cross"]) * placement
	var knee_angle := float(profile["plie_angle"]) * depth
	var leg_length := _idle_leg_length()

	var left_foot := _bone_index("left_foot")
	var right_foot := _bone_index("right_foot")
	var left_toe := _bone_index("left_toe")
	var right_toe := _bone_index("right_toe")
	var left_foot_target := _bone_world_position(left_foot)
	var right_foot_target := _bone_world_position(right_foot)
	var left_toe_length := maxf(
		_bone_world_position(left_foot).distance_to(_bone_world_position(left_toe)),
		0.001
	)
	var right_toe_length := maxf(
		_bone_world_position(right_foot).distance_to(_bone_world_position(right_toe)),
		0.001
	)

	# Lower the pelvis because the leg chain folds, while preserving the original
	# floor contact points as explicit world-space targets.
	var derived_drop := leg_length * (1.0 - cos(knee_angle))
	var max_drop := leg_length * float(profile["root_drop_ratio"])
	_model_root.position.y = (
		_model_base_transform.origin.y
		- minf(derived_drop, max_drop)
	)
	_model_root.position.x = (
		_model_base_transform.origin.x
		+ support_side
		* float(profile["weight_shift"])
		* placement
		* (1.0 - 0.30 * depth)
		* (1.0 - settle)
	)

	var audience_forward := Vector3(0.0, 0.0, 1.0)
	for left in [true, false]:
		var side := left_leg_side if left else right_leg_side
		var is_working: bool = left != support_left
		var hip := _bone_index("left_upper_leg" if left else "right_upper_leg")
		var knee := _bone_index("left_lower_leg" if left else "right_lower_leg")
		var foot := left_foot if left else right_foot
		var toe := left_toe if left else right_toe
		if hip < 0 or knee < 0 or foot < 0:
			continue

		var outward := Vector3(side, 0.0, 0.0)
		var floor_target := left_foot_target if left else right_foot_target
		if is_working:
			# A small crossed placement gives readable weight transfer without
			# turning the bow into a large travelling step.
			floor_target += -outward * working_cross * leg_length

		var hip_position := _bone_world_position(hip)
		var knee_target := hip_position.lerp(floor_target, 0.52)
		knee_target += (
			outward
			* leg_length
			* (0.045 * placement + 0.145 * depth + 0.075 * turnout)
		)
		knee_target += (
			audience_forward
			* leg_length
			* (0.025 * placement + 0.045 * depth)
		)
		knee_target += Vector3.UP * leg_length * 0.035 * depth

		# Audience readability comes from the knee moving visibly OUT over the
		# turned-out toe while the shin folds back toward the planted foot.
		_steer_segment_toward_world_point(
			hip,
			knee,
			knee_target,
			0.96
		)
		_steer_segment_toward_world_point(
			knee,
			foot,
			floor_target,
			0.98
		)

		if toe >= 0:
			var toe_length := left_toe_length if left else right_toe_length
			var toe_direction := (
				outward * (0.30 + turnout * 0.60)
				+ audience_forward * 0.95
				- Vector3.UP * 0.025
			).normalized()
			var toe_target := floor_target + toe_direction * toe_length
			_steer_segment_toward_world_point(
				foot,
				toe,
				toe_target,
				0.82
			)



func _apply_reverence_clavicle_support(
	profile: Dictionary,
	elapsed: float,
	variant: StringName
) -> void:
	var place_end := float(profile["place_end"])
	var plie_end := float(profile["plie_end"])
	var rise_end := float(profile["rise_end"])
	var expressive_left := bool(profile["expressive_left"])
	var final_variant: bool = variant == FINAL_REVERENCE
	var engage := smoothstep(0.18, place_end + 0.10, elapsed)
	var release := smoothstep(plie_end + 0.16, rise_end + 0.06, elapsed)
	var phrase_alpha := engage * (1.0 - release)
	if phrase_alpha <= 0.001:
		return

	var chest := _bone_index("chest")
	var chest_position := _bone_world_position(chest)
	for left in [true, false]:
		var clavicle := _bone_index("left_clavicle" if left else "right_clavicle")
		var shoulder := _bone_index("left_upper_arm" if left else "right_upper_arm")
		if clavicle < 0 or shoulder < 0:
			continue

		var expressive: bool = final_variant and left == expressive_left
		var clavicle_position := _bone_world_position(clavicle)
		var shoulder_position := _bone_world_position(shoulder)
		var clavicle_length := maxf(
			clavicle_position.distance_to(shoulder_position),
			0.001
		)
		var outward := shoulder_position - chest_position
		outward -= Vector3.UP * outward.dot(Vector3.UP)
		if outward.length_squared() <= 0.000001:
			outward = Vector3(-1.0 if left else 1.0, 0.0, 0.0)
		outward = outward.normalized()

		# The clavicle carries the arm without becoming a visible shrug.
		var lift := 0.035
		if final_variant:
			lift = 0.090
		if expressive:
			lift += 0.025
		var target_direction := (
			outward
			+ Vector3.UP * lift
			+ Vector3(0.0, 0.0, 0.08)
		).normalized()
		var shoulder_target := (
			clavicle_position
			+ target_direction * clavicle_length
		)
		var strength := (0.18 if final_variant else 0.12) * phrase_alpha
		_steer_segment_toward_world_point(
			clavicle,
			shoulder,
			shoulder_target,
			strength
		)


func _apply_reverence_port_de_bras(
	profile: Dictionary,
	elapsed: float,
	variant: StringName
) -> void:
	var place_end := float(profile["place_end"])
	var plie_end := float(profile["plie_end"])
	var rise_end := float(profile["rise_end"])
	var expressive_left := bool(profile["expressive_left"])
	var opening_variant: bool = variant == OPENING_REVERENCE
	var final_variant: bool = variant == FINAL_REVERENCE
	var upper_gather := smoothstep(0.10, place_end * 0.92, elapsed)
	var hand_gather := smoothstep(0.16, place_end, elapsed)
	var upper_present := smoothstep(place_end * 0.62, plie_end - 0.12, elapsed)
	var hand_present := smoothstep(place_end * 0.78, plie_end + 0.02, elapsed)
	var upper_resolve := smoothstep(plie_end + 0.05, rise_end, elapsed)
	var hand_resolve := smoothstep(plie_end + 0.12, rise_end + 0.10, elapsed)

	var left_shoulder := _bone_index("left_upper_arm")
	var right_shoulder := _bone_index("right_upper_arm")
	var chest := _bone_index("chest")
	var head := _bone_index("head")
	var chest_position := _bone_world_position(chest)
	var head_position := _bone_world_position(head)
	var shoulder_center := chest_position
	if left_shoulder >= 0 and right_shoulder >= 0:
		shoulder_center = (
			_bone_world_position(left_shoulder)
			+ _bone_world_position(right_shoulder)
		) * 0.5

	for left in [true, false]:
		var expressive: bool = final_variant and left == expressive_left
		var shoulder := left_shoulder if left else right_shoulder
		var elbow := _bone_index("left_lower_arm" if left else "right_lower_arm")
		var hand := _bone_index("left_hand" if left else "right_hand")
		var middle := _bone_index("left_middle" if left else "right_middle")
		if shoulder < 0 or elbow < 0:
			continue

		var shoulder_position := _bone_world_position(shoulder)
		var elbow_position := _bone_world_position(elbow)
		var outward := shoulder_position - shoulder_center
		outward -= Vector3.UP * outward.dot(Vector3.UP)
		if outward.length_squared() <= 0.000001:
			var fallback_side := -1.0 if left else 1.0
			outward = Vector3(fallback_side, 0.0, 0.0)
		outward = outward.normalized()

		var upper_length := maxf(
			shoulder_position.distance_to(elbow_position),
			0.001
		)
		var forearm_length := upper_length * 0.92
		if hand >= 0:
			forearm_length = maxf(
				elbow_position.distance_to(_bone_world_position(hand)),
				0.001
			)
		var reach := upper_length + forearm_length
		var audience_forward := Vector3(0.0, 0.0, 1.0)

		var prep_elbow := (
			shoulder_position
			+ outward * upper_length * 0.36
			- Vector3.UP * upper_length * 0.42
			+ audience_forward * upper_length * 0.16
		)
		var prep_hand := (
			shoulder_center
			+ outward * reach * 0.20
			- Vector3.UP * reach * 0.46
			+ audience_forward * reach * 0.28
		)
		var gathered_elbow := (
			shoulder_position
			+ outward * upper_length * 0.50
			- Vector3.UP * upper_length * 0.20
			+ audience_forward * upper_length * 0.16
		)
		var gathered_hand := (
			shoulder_center
			+ outward * reach * 0.16
			- Vector3.UP * reach * 0.26
			+ audience_forward * reach * 0.28
		)

		var peak_elbow: Vector3
		var peak_hand: Vector3
		var settle_elbow: Vector3
		var settle_hand: Vector3
		if opening_variant:
			# North Star: symmetric fifth-position-en-avant family.
			# Shoulders stay quiet; elbows sit clearly below shoulder level;
			# forearms return inward to create one continuous oval in front
			# of the lower sternum/upper abdomen.
			peak_elbow = (
				shoulder_position
				+ outward * upper_length * 0.48
				- Vector3.UP * upper_length * 0.32
				+ audience_forward * upper_length * 0.18
			)
			peak_hand = (
				shoulder_center
				+ outward * reach * 0.03
				- Vector3.UP * reach * 0.43
				+ audience_forward * reach * 0.32
			)
			settle_elbow = (
				shoulder_position
				+ outward * upper_length * 0.46
				- Vector3.UP * upper_length * 0.34
				+ audience_forward * upper_length * 0.16
			)
			settle_hand = (
				shoulder_center
				+ outward * reach * 0.02
				- Vector3.UP * reach * 0.45
				+ audience_forward * reach * 0.28
			)
		elif final_variant and expressive:
			peak_elbow = (
				shoulder_position
				+ outward * upper_length * 0.48
				+ Vector3.UP * upper_length * 0.68
				+ audience_forward * upper_length * 0.12
			)
			peak_hand = (
				head_position
				+ outward * reach * 0.14
				+ Vector3.UP * reach * 0.14
				+ audience_forward * reach * 0.22
			)
			settle_elbow = (
				shoulder_position
				+ outward * upper_length * 0.70
				- Vector3.UP * upper_length * 0.04
				+ audience_forward * upper_length * 0.16
			)
			settle_hand = (
				shoulder_center
				+ outward * reach * 0.20
				- Vector3.UP * reach * 0.18
				+ audience_forward * reach * 0.34
			)
		elif final_variant:
			peak_elbow = (
				shoulder_position
				+ outward * upper_length * 0.92
				+ Vector3.UP * upper_length * 0.08
				+ audience_forward * upper_length * 0.10
			)
			peak_hand = (
				shoulder_center
				+ outward * reach * 0.54
				+ Vector3.UP * reach * 0.02
				+ audience_forward * reach * 0.30
			)
			settle_elbow = (
				shoulder_position
				+ outward * upper_length * 0.72
				- Vector3.UP * upper_length * 0.06
				+ audience_forward * upper_length * 0.16
			)
			settle_hand = (
				shoulder_center
				+ outward * reach * 0.24
				- Vector3.UP * reach * 0.18
				+ audience_forward * reach * 0.34
			)
		elif expressive:
			peak_elbow = (
				shoulder_position
				+ outward * upper_length * 0.68
				- Vector3.UP * upper_length * 0.10
				+ audience_forward * upper_length * 0.16
			)
			peak_hand = (
				shoulder_center
				+ outward * reach * 0.34
				- Vector3.UP * reach * 0.18
				+ audience_forward * reach * 0.30
			)
			settle_elbow = (
				shoulder_position
				+ outward * upper_length * 0.58
				- Vector3.UP * upper_length * 0.16
				+ audience_forward * upper_length * 0.16
			)
			settle_hand = (
				shoulder_center
				+ outward * reach * 0.28
				- Vector3.UP * reach * 0.24
				+ audience_forward * reach * 0.30
			)
		else:
			peak_elbow = (
				shoulder_position
				+ outward * upper_length * 0.50
				- Vector3.UP * upper_length * 0.16
				+ audience_forward * upper_length * 0.18
			)
			peak_hand = (
				shoulder_center
				+ outward * reach * 0.16
				- Vector3.UP * reach * 0.26
				+ audience_forward * reach * 0.32
			)
			settle_elbow = (
				shoulder_position
				+ outward * upper_length * 0.50
				- Vector3.UP * upper_length * 0.18
				+ audience_forward * upper_length * 0.16
			)
			settle_hand = (
				shoulder_center
				+ outward * reach * 0.20
				- Vector3.UP * reach * 0.26
				+ audience_forward * reach * 0.30
			)

		var elbow_target := prep_elbow.lerp(gathered_elbow, upper_gather)
		elbow_target = elbow_target.lerp(peak_elbow, upper_present)
		elbow_target = elbow_target.lerp(settle_elbow, upper_resolve)
		var hand_target := prep_hand.lerp(gathered_hand, hand_gather)
		hand_target = hand_target.lerp(peak_hand, hand_present)
		hand_target = hand_target.lerp(settle_hand, hand_resolve)

		# Once the presentation opens, the hand may not collapse to waist level.
		# This is a world-space silhouette constraint, not a guessed local Euler.
		if hand_present > 0.20:
			var hand_floor_ratio := 0.40 if opening_variant else 0.30
			var classical_hand_floor := (
				shoulder_center.y - reach * hand_floor_ratio
			)
			hand_target.y = maxf(hand_target.y, classical_hand_floor)

		_steer_segment_toward_world_point(
			shoulder,
			elbow,
			elbow_target,
			0.97
		)
		if hand >= 0:
			_steer_segment_toward_world_point(
				elbow,
				hand,
				hand_target,
				0.97
			)
			if middle >= 0:
				var hand_position := _bone_world_position(hand)
				var middle_position := _bone_world_position(middle)
				var hand_axis_length := maxf(
					hand_position.distance_to(middle_position),
					0.001
				)
				var wrist_lift := 0.10
				if final_variant and expressive:
					wrist_lift = 0.18
				var hand_finish_direction: Vector3
				if opening_variant:
					hand_finish_direction = (
						-outward * 0.96
						+ audience_forward * 0.16
						- Vector3.UP * 0.05
					).normalized()
				else:
					hand_finish_direction = (
						-outward * (0.74 if expressive else 0.66)
						+ audience_forward * 0.28
						+ Vector3.UP * wrist_lift
					).normalized()
				var hand_finish_target := (
					hand_position
					+ hand_finish_direction * hand_axis_length
				)
				var hand_finish_strength := (
					0.22
					+ 0.22 * hand_present
					- 0.06 * hand_resolve
				)
				_steer_segment_toward_world_point(
					hand,
					middle,
					hand_finish_target,
					clampf(hand_finish_strength, 0.16, 0.42)
				)

func _apply_reverence_epaulement(profile: Dictionary, elapsed: float) -> void:
	var place_end := float(profile["place_end"])
	var plie_end := float(profile["plie_end"])
	var rise_end := float(profile["rise_end"])
	var settle_end := float(profile["settle_end"])
	var expressive_left := bool(profile["expressive_left"])
	var expressive_side := _audience_pair_side_sign(
		_bone_index("left_upper_arm"),
		_bone_index("right_upper_arm")
	)
	if not expressive_left:
		expressive_side = -expressive_side

	var torso_in := smoothstep(place_end * 0.82, plie_end - 0.10, elapsed)
	var torso_out := smoothstep(plie_end + 0.04, rise_end - 0.04, elapsed)
	var torso_ack := torso_in * (1.0 - torso_out)
	var head_in := smoothstep(place_end + 0.10, plie_end + 0.04, elapsed)
	var head_out := smoothstep(rise_end - 0.08, settle_end, elapsed)
	var head_ack := head_in * (1.0 - head_out)

	# The trunk stays lifted; head/épaulement joins slightly later and resolves
	# later than the arms, preserving a classical acknowledgement rather than a
	# deep waist bow.
	_steer_segment_world_direction(
		_bone_index("pelvis"),
		_bone_index("chest"),
		Vector3(
			expressive_side * 0.012 * torso_ack,
			0.999,
			float(profile["torso_ack"]) * torso_ack
		).normalized(),
		0.84
	)
	_steer_segment_world_direction(
		_bone_index("chest"),
		_bone_index("head"),
		Vector3(
			expressive_side * 0.050 * head_ack,
			0.995,
			float(profile["head_ack"]) * head_ack
		).normalized(),
		0.80
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
	var previous_position := 0.0
	if previous_animation != &"":
		previous_position = _animation_player.current_animation_position
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
		"left_clavicle": _find_bone(["leftclavicle", "claviclel", "shoulderl"]),
		"right_clavicle": _find_bone(["rightclavicle", "clavicler", "shoulderr"]),
		"left_upper_arm": _find_bone(["leftupperarm", "upperarml", "leftarm", "arml"]),
		"left_lower_arm": _find_bone(["leftlowerarm", "lowerarml", "leftforearm", "forearml"]),
		"left_hand": _find_bone(["lefthand", "handl"]),
		"left_middle": _find_bone(["leftmiddle", "middlel", "middlefingerl"]),
		"right_upper_arm": _find_bone(["rightupperarm", "upperarmr", "rightarm", "armr"]),
		"right_lower_arm": _find_bone(["rightlowerarm", "lowerarmr", "rightforearm", "forearmr"]),
		"right_hand": _find_bone(["righthand", "handr"]),
		"right_middle": _find_bone(["rightmiddle", "middler", "middlefingerr"]),
		"left_upper_leg": _find_bone(["leftupperleg", "upperlegl", "leftupleg", "leftthigh", "thighl"]),
		"left_lower_leg": _find_bone(["leftlowerleg", "lowerlegl", "leftleg", "leftcalf", "calfl", "leftshin", "shinl"]),
		"left_foot": _find_bone(["leftfoot", "footl"]),
		"left_toe": _find_bone(["lefttoebase", "lefttoe", "lefttoes", "toesl", "toel"]),
		"right_upper_leg": _find_bone(["rightupperleg", "upperlegr", "rightupleg", "rightthigh", "thighr"]),
		"right_lower_leg": _find_bone(["rightlowerleg", "lowerlegr", "rightleg", "rightcalf", "calfr", "rightshin", "shinr"]),
		"right_foot": _find_bone(["rightfoot", "footr"]),
		"right_toe": _find_bone(["righttoebase", "righttoe", "righttoes", "toesr", "toer"]),
	}

	# Stage gestures require a true distal arm joint. Some imported rigs use
	# opaque/prefixed hand names, so infer the terminal joint from the already
	# resolved forearm chain only when name resolution failed.
	if int(_bones["left_hand"]) < 0:
		_bones["left_hand"] = _infer_distal_joint_from_chain(
			int(_bones["left_lower_arm"])
		)
	if int(_bones["right_hand"]) < 0:
		_bones["right_hand"] = _infer_distal_joint_from_chain(
			int(_bones["right_lower_arm"])
		)

	if int(_bones["left_hand"]) < 0 or int(_bones["right_hand"]) < 0:
		push_warning(
			"Humanoid stage hand chain unresolved: left=%s right=%s"
			% [
				_bone_debug_name(int(_bones["left_hand"])),
				_bone_debug_name(int(_bones["right_hand"])),
			]
		)




func _infer_distal_joint_from_chain(start_idx: int) -> int:
	if start_idx < 0:
		return -1

	var current := start_idx
	for _depth in range(4):
		var only_child := -1
		var child_count := 0
		for bone_idx in range(_skeleton.get_bone_count()):
			if _skeleton.get_bone_parent(bone_idx) == current:
				child_count += 1
				only_child = bone_idx
				if child_count > 1:
					break
		if child_count != 1:
			break
		current = only_child

	return current if current != start_idx else -1


func _bone_debug_name(bone_idx: int) -> String:
	if bone_idx < 0 or bone_idx >= _skeleton.get_bone_count():
		return "<unresolved>"
	return "%s[%d]" % [String(_skeleton.get_bone_name(bone_idx)), bone_idx]


func _find_bone(aliases: Array[String]) -> int:
	var normalized_aliases: Array[String] = []
	for alias in aliases:
		normalized_aliases.append(_normalize_bone_name(alias))

	# Exact names remain authoritative so existing successfully resolved gait
	# chains cannot silently remap.
	for bone_idx in range(_skeleton.get_bone_count()):
		var normalized := _normalize_bone_name(
			String(_skeleton.get_bone_name(bone_idx))
		)
		if normalized in normalized_aliases:
			return bone_idx

	# Imported rigs often prepend an Armature/Rig/mixamorig1 namespace. Only use
	# a sufficiently specific suffix fallback after exact matching failed.
	for bone_idx in range(_skeleton.get_bone_count()):
		var normalized := _normalize_bone_name(
			String(_skeleton.get_bone_name(bone_idx))
		)
		for alias in normalized_aliases:
			if alias.length() >= 6 and normalized.ends_with(alias):
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


func _steer_segment_toward_world_point(
	parent_idx: int,
	child_idx: int,
	target_world_position: Vector3,
	strength: float
) -> void:
	if parent_idx < 0 or child_idx < 0:
		return
	var parent_world_position := _bone_world_position(parent_idx)
	var desired_world_direction := target_world_position - parent_world_position
	_steer_segment_world_direction(
		parent_idx,
		child_idx,
		desired_world_direction,
		strength
	)


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
