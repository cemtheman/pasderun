extends Node

signal runtime_started

enum PreludeState {
	WALK_IN,
	BOW,
	READY,
	EXIT_TURN,
	STARTED,
}

@export var dancer: CharacterBody3D
@export var music_root: Node
@export var audio_player: AudioStreamPlayer
@export var flow_tracker: Node
@export var tap_timing_debug: Node
@export var accent_runtime_trace: Node
@export var overlay: CanvasLayer

@export var entrance_target_x := 0.0
@export var entrance_walk_distance := 3.0
@export var entrance_speed := 1.55
@export var bow_duration := 2.25

var _started := false
var _prelude_state := PreludeState.WALK_IN
var _bow_elapsed := 0.0
var _exit_turn_elapsed := 0.0
var _exit_turn_duration := 0.38
var _stage_visual: Node


func _ready() -> void:
	if (
		dancer == null
		or music_root == null
		or audio_player == null
		or flow_tracker == null
		or tap_timing_debug == null
		or accent_runtime_trace == null
		or overlay == null
	):
		push_error("RuntimeStartGate requires all runtime and overlay references.")
		set_process(false)
		set_process_input(false)
		return

	audio_player.stop()
	music_root.process_mode = Node.PROCESS_MODE_DISABLED
	flow_tracker.process_mode = Node.PROCESS_MODE_DISABLED
	tap_timing_debug.process_mode = Node.PROCESS_MODE_DISABLED
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_DISABLED

	# The curtain is open for the silent stage entrance. Start offstage-left of
	# the presentation mark so the dancer visibly WALKS in before turning to the
	# audience for the révérence. The start prompt appears only after the walk,
	# turn, curtsy and ready settle are complete.
	overlay.visible = false
	dancer.process_mode = Node.PROCESS_MODE_INHERIT
	var entrance_start := dancer.global_position
	entrance_start.x = entrance_target_x - maxf(entrance_walk_distance, 0.0)
	dancer.global_position = entrance_start
	if dancer.has_method("begin_stage_entrance"):
		dancer.call("begin_stage_entrance", entrance_speed)
	else:
		push_error("RuntimeStartGate requires Dancer stage-entrance support.")
		set_process(false)
		return

	call_deferred("_resolve_stage_visual")


func _process(delta: float) -> void:
	if _prelude_state == PreludeState.STARTED:
		return

	_resolve_stage_visual()

	if _prelude_state == PreludeState.WALK_IN:
		_set_stage_visual(&"WALK")
		if dancer.global_position.x >= entrance_target_x:
			var settled := dancer.global_position
			settled.x = entrance_target_x
			dancer.global_position = settled
			if dancer.has_method("set_stage_entrance_speed"):
				dancer.call("set_stage_entrance_speed", 0.0)
			_prelude_state = PreludeState.BOW
			_bow_elapsed = 0.0
			_set_stage_visual(&"BOW")
		return

	if _prelude_state == PreludeState.BOW:
		_bow_elapsed += delta
		if _bow_elapsed >= bow_duration:
			_prelude_state = PreludeState.READY
			_set_stage_visual(&"READY")
			overlay.visible = true
		return

	if _prelude_state == PreludeState.EXIT_TURN:
		_exit_turn_elapsed += delta
		if _exit_turn_elapsed >= _exit_turn_duration:
			_enable_gameplay_after_exit_turn()


func _input(event: InputEvent) -> void:
	if (
		_started
		or _prelude_state != PreludeState.READY
		or not _is_valid_start_event(event)
	):
		return

	_started = true
	_prelude_state = PreludeState.EXIT_TURN
	_exit_turn_elapsed = 0.0
	get_viewport().set_input_as_handled()

	# Web audio must still be unlocked synchronously inside the user gesture.
	music_root.process_mode = Node.PROCESS_MODE_INHERIT
	flow_tracker.process_mode = Node.PROCESS_MODE_INHERIT
	tap_timing_debug.process_mode = Node.PROCESS_MODE_INHERIT
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_INHERIT
	# Unlock Web audio synchronously inside the user gesture, but keep playback
	# paused at 0 while the dancer turns from the audience toward +X travel.
	audio_player.play(0.0)
	audio_player.stream_paused = true
	overlay.visible = false

	_resolve_stage_visual()
	if (
		_stage_visual != null
		and _stage_visual.has_method("get_stage_exit_turn_duration")
	):
		_exit_turn_duration = maxf(
			float(_stage_visual.call("get_stage_exit_turn_duration")),
			0.0
		)
	_set_stage_visual(&"EXIT_TURN")


func _enable_gameplay_after_exit_turn() -> void:
	if _prelude_state != PreludeState.EXIT_TURN:
		return

	_prelude_state = PreludeState.STARTED
	if dancer.has_method("end_stage_entrance"):
		dancer.call("end_stage_entrance")
	_resolve_stage_visual()
	if _stage_visual != null and _stage_visual.has_method("clear_stage_presentation"):
		_stage_visual.call("clear_stage_presentation")
	# play() was used only to unlock Web audio inside the input gesture.
	# Rewind at the actual post-turn gameplay boundary so the first run frame
	# and music t=0 share the same release point.
	audio_player.seek(0.0)
	runtime_started.emit()
	audio_player.stream_paused = false
	set_process_input(false)


func _resolve_stage_visual() -> void:
	if is_instance_valid(_stage_visual):
		return
	_stage_visual = dancer.get_node_or_null("BallerinaVisualV1")


func _set_stage_visual(stage: StringName) -> void:
	_resolve_stage_visual()
	if _stage_visual != null and _stage_visual.has_method("set_stage_presentation_state"):
		_stage_visual.call("set_stage_presentation_state", stage)


func _is_valid_start_event(event: InputEvent) -> bool:
	if event is InputEventScreenTouch:
		return event.pressed
	if event is InputEventMouseButton:
		return event.pressed and event.button_index == MOUSE_BUTTON_LEFT
	if event is InputEventKey:
		if not event.pressed or event.echo:
			return false
		return event.keycode == KEY_SPACE or event.keycode == KEY_ENTER
	return false
