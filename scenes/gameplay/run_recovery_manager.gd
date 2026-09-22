extends Node

signal checkpoint_changed(checkpoint_id: String, checkpoint_index: int, checkpoint_position: Vector3)

const DEATH_Y := -6.0
const RUN_SPEED := 4.0
const CHECKPOINT_SURFACE_Y := -2.8
const DANCER_STANDING_OFFSET := 1.5

enum RunState {
	PLAYING,
	DEAD,
	COMPLETION_CEREMONY,
	LEVEL_COMPLETE,
}

enum CompletionPhase {
	NONE,
	DECELERATE_TO_WALK,
	WALK_TO_MARK,
	FINAL_BOW,
}

const COMPLETION_WALK_SPEED := 1.45
# The MP3 container lasts 140.016 s, but the analyzed musical energy collapses
# before that. Treat 137.75 s as the choreographic end cue and leave the quiet
# encoded tail untouched for playback integrity.
const COMPLETION_MUSICAL_END_TIME := 137.75
const COMPLETION_DECEL_DURATION := 1.20
const COMPLETION_APPROACH_DISTANCE := 1.35
const COMPLETION_WALK_VISUAL_SWITCH := 0.65
const COMPLETION_FINAL_BOW_DURATION := 2.85

const CHECKPOINTS := [
	{"id": "START", "x": 0.0},
	{"id": "POST_FORK_01", "x": 201.0},
	{"id": "POST_FORK_02", "x": 276.0},
	{"id": "POST_FORK_03", "x": 356.0},
	{"id": "POST_FORK_04", "x": 436.0},
	{"id": "POST_FORK_05", "x": 535.0},
]

@export var dancer: CharacterBody3D
@export var camera_rig: Node3D
@export var fork_camera_controller: Node
@export var start_gate: Node
@export var music_root: Node
@export var audio_player: AudioStreamPlayer
@export var flow_tracker: Node
@export var tap_timing_debug: Node
@export var accent_runtime_trace: Node
@export var game_over_overlay: CanvasLayer
@export var continue_button: Button
@export var restart_button: Button
@export var exit_button: Button
@export var completion_trigger: Marker3D
@export var level_complete_overlay: CanvasLayer
@export var next_level_button: Button
@export var main_menu_button: Button
@export var next_level_status: Label
@export var checkpoint_status_label: Label
@export var next_level_scene: PackedScene

var _state := RunState.PLAYING
var _run_started := false
var _checkpoint_index := 0
var _checkpoint_position := Vector3.ZERO
var _checkpoint_music_time := 0.0
var _completion_phase := CompletionPhase.NONE
var _completion_phase_elapsed := 0.0
var _completion_bow_x := 0.0
var _completion_decel_start_x := 0.0
var _completion_decel_start_speed := RUN_SPEED
var _ballerina_visual: Node


func _ready() -> void:
	if not _references_valid():
		push_error("RunRecoveryManager requires all runtime and Game Over references.")
		set_physics_process(false)
		return
	_checkpoint_position = dancer.global_position
	game_over_overlay.visible = false
	level_complete_overlay.visible = false
	continue_button.pressed.connect(_continue_from_checkpoint)
	restart_button.pressed.connect(_restart_run)
	exit_button.pressed.connect(_exit_run)
	next_level_button.pressed.connect(_load_next_level)
	main_menu_button.pressed.connect(_return_to_main_menu)
	start_gate.connect("runtime_started", Callable(self, "_on_runtime_started"))
	if not audio_player.finished.is_connected(_on_music_finished):
		audio_player.finished.connect(_on_music_finished)
	next_level_button.disabled = next_level_scene == null
	next_level_status.visible = next_level_scene == null
	_update_checkpoint_status()


func _physics_process(delta: float) -> void:
	if not _run_started:
		return
	if _state == RunState.COMPLETION_CEREMONY:
		_update_completion_ceremony(delta)
		return
	if _state != RunState.PLAYING:
		return

	# Begin the run->walk handoff from the analyzed musical end cue, not the MP3
	# container duration. The encoded quiet tail may continue playing, but the
	# dancer should already read the phrase as finished.
	if _should_begin_completion_lead():
		_begin_completion_ceremony()
		return

	# Spatial completion remains a safety fallback if the stream has already
	# ended without the lead transition being armed.
	if (
		dancer.global_position.x >= completion_trigger.global_position.x
		and not audio_player.playing
	):
		_begin_completion_ceremony()
		return
	if dancer.global_position.y < DEATH_Y:
		_enter_dead_state()
		return
	_update_checkpoint()


func continue_is_allowed() -> bool:
	return true


func continue_cost() -> int:
	return 0


func consume_continue_cost() -> void:
	pass


func get_checkpoint_id() -> String:
	return String(CHECKPOINTS[_checkpoint_index]["id"])


func get_run_state() -> String:
	return RunState.keys()[_state]


func _on_runtime_started() -> void:
	_run_started = true
	_checkpoint_index = 0
	_checkpoint_position = dancer.global_position
	_checkpoint_music_time = 0.0
	_update_checkpoint_status()
	checkpoint_changed.emit(
		get_checkpoint_id(),
		_checkpoint_index,
		_checkpoint_position
	)


func _on_music_finished() -> void:
	if not _run_started or _state != RunState.PLAYING:
		return
	_begin_completion_ceremony()


func _should_begin_completion_lead() -> bool:
	if audio_player == null or audio_player.stream == null:
		return false
	if not audio_player.playing:
		return false

	var lead_start := maxf(
		COMPLETION_MUSICAL_END_TIME - COMPLETION_DECEL_DURATION,
		0.0
	)
	return audio_player.get_playback_position() >= lead_start


func _update_checkpoint() -> void:
	var next_index := _checkpoint_index + 1
	if next_index >= CHECKPOINTS.size():
		return
	var candidate: Dictionary = CHECKPOINTS[next_index]
	if dancer.global_position.x < float(candidate["x"]):
		return
	if not dancer.is_on_floor() or bool(dancer.get("has_fallen")):
		return
	if not bool(fork_camera_controller.call("is_outside_fork")):
		return

	_checkpoint_index = next_index
	# Capture the actual grounded position after the threshold has been crossed.
	# A checkpoint candidate may fall inside a generated fork or on a reshaped
	# spatial surface; replaying its nominal X/Y would respawn the dancer inside
	# route geometry or below/above the real runway.
	_checkpoint_position = dancer.global_position
	_checkpoint_music_time = dancer.global_position.x / RUN_SPEED
	_update_checkpoint_status()
	checkpoint_changed.emit(
		get_checkpoint_id(),
		_checkpoint_index,
		_checkpoint_position
	)


func _checkpoint_display_name() -> String:
	if _checkpoint_index <= 0:
		return "START"
	return "CHECKPOINT %d" % _checkpoint_index


func _update_checkpoint_status() -> void:
	if checkpoint_status_label != null:
		checkpoint_status_label.text = "RETURN TO %s" % _checkpoint_display_name()


func _enter_dead_state() -> void:
	_state = RunState.DEAD
	fork_camera_controller.call("set_frozen", true)
	camera_rig.process_mode = Node.PROCESS_MODE_DISABLED
	dancer.process_mode = Node.PROCESS_MODE_DISABLED
	audio_player.stop()
	music_root.process_mode = Node.PROCESS_MODE_DISABLED
	flow_tracker.process_mode = Node.PROCESS_MODE_DISABLED
	tap_timing_debug.process_mode = Node.PROCESS_MODE_DISABLED
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_DISABLED
	_update_checkpoint_status()
	game_over_overlay.visible = true
	continue_button.grab_focus()


func _continue_from_checkpoint() -> void:
	if _state != RunState.DEAD or not continue_is_allowed():
		return
	consume_continue_cost()
	game_over_overlay.visible = false
	_restore_dancer()
	fork_camera_controller.call("restore_normal_state")
	camera_rig.process_mode = Node.PROCESS_MODE_INHERIT
	if camera_rig.has_method("reset_to_target"):
		camera_rig.reset_to_target()
	music_root.process_mode = Node.PROCESS_MODE_INHERIT
	flow_tracker.process_mode = Node.PROCESS_MODE_INHERIT
	tap_timing_debug.process_mode = Node.PROCESS_MODE_INHERIT
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_INHERIT
	audio_player.stop()
	audio_player.play(_checkpoint_music_time)
	dancer.process_mode = Node.PROCESS_MODE_INHERIT
	_state = RunState.PLAYING


func _begin_completion_ceremony() -> void:
	if _state != RunState.PLAYING:
		return

	_state = RunState.COMPLETION_CEREMONY
	_completion_phase = CompletionPhase.DECELERATE_TO_WALK
	_completion_phase_elapsed = 0.0
	_completion_decel_start_x = dancer.global_position.x
	_completion_decel_start_speed = maxf(
		absf(dancer.velocity.x),
		COMPLETION_WALK_SPEED
	)
	# Let the dancer finish the musical deceleration naturally, then take only a
	# short walk into the bow. Do not force her back to the old X=music-end mark;
	# that would turn the speed lost during deceleration into an artificial long
	# post-music walk.
	_completion_bow_x = (
		_completion_decel_start_x
		+ COMPLETION_DECEL_DURATION
		* 0.5
		* (_completion_decel_start_speed + COMPLETION_WALK_SPEED)
		+ COMPLETION_APPROACH_DISTANCE
	)

	fork_camera_controller.call("restore_normal_state")
	# Keep following the dancer through the music-end deceleration and walk.
	# Freeze only at the bow mark so the révérence and wing exit share one frame.
	fork_camera_controller.call("set_frozen", false)

	flow_tracker.process_mode = Node.PROCESS_MODE_DISABLED
	tap_timing_debug.process_mode = Node.PROCESS_MODE_DISABLED
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_DISABLED
	game_over_overlay.visible = false
	level_complete_overlay.visible = false

	_ballerina_visual = dancer.get_node_or_null("BallerinaVisualV1")
	if dancer.has_method("begin_stage_ending"):
		dancer.call(
			"begin_stage_ending",
			_completion_decel_start_speed
		)

	# Start in RUN, but switch the visual gait before the soundtrack ends so no
	# running animation survives into the silent closing walk.
	_set_completion_stage_visual(&"RUN")


func _update_completion_ceremony(delta: float) -> void:
	_completion_phase_elapsed += delta

	match _completion_phase:
		CompletionPhase.DECELERATE_TO_WALK:
			var t := clampf(
				_completion_phase_elapsed / COMPLETION_DECEL_DURATION,
				0.0,
				1.0
			)
			var eased := smoothstep(0.0, 1.0, t)
			var speed := lerpf(
				_completion_decel_start_speed,
				COMPLETION_WALK_SPEED,
				eased
			)
			if dancer.has_method("set_stage_ending_speed"):
				dancer.call("set_stage_ending_speed", speed)
			if t >= COMPLETION_WALK_VISUAL_SWITCH:
				_set_completion_stage_visual(&"WALK")
			if t < 1.0:
				return

			_completion_phase = CompletionPhase.WALK_TO_MARK
			_completion_phase_elapsed = 0.0
			_set_completion_stage_visual(&"WALK")
			if dancer.has_method("set_stage_ending_speed"):
				dancer.call(
					"set_stage_ending_speed",
					COMPLETION_WALK_SPEED
				)

		CompletionPhase.WALK_TO_MARK:
			if dancer.global_position.x < _completion_bow_x:
				return
			var bow_mark := dancer.global_position
			bow_mark.x = _completion_bow_x
			dancer.global_position = bow_mark
			if dancer.has_method("set_stage_ending_speed"):
				dancer.call("set_stage_ending_speed", 0.0)
			_completion_phase = CompletionPhase.FINAL_BOW
			_completion_phase_elapsed = 0.0
			fork_camera_controller.call("set_frozen", true)
			_set_completion_stage_visual(&"FINAL_BOW")

		CompletionPhase.FINAL_BOW:
			if _completion_phase_elapsed < COMPLETION_FINAL_BOW_DURATION:
				return
			# Hold the settled audience-facing reverence as the terminal stage
			# image. Do not turn away or resume locomotion after the bow.
			_finish_level_complete_state()


func _set_completion_stage_visual(stage: StringName) -> void:
	if (
		_ballerina_visual != null
		and _ballerina_visual.has_method("set_stage_presentation_state")
	):
		_ballerina_visual.call("set_stage_presentation_state", stage)


func _finish_level_complete_state() -> void:
	_completion_phase = CompletionPhase.NONE
	_completion_phase_elapsed = 0.0
	_state = RunState.LEVEL_COMPLETE
	audio_player.stop()
	music_root.process_mode = Node.PROCESS_MODE_DISABLED
	camera_rig.process_mode = Node.PROCESS_MODE_DISABLED
	dancer.process_mode = Node.PROCESS_MODE_DISABLED
	game_over_overlay.visible = false
	level_complete_overlay.visible = true
	if next_level_button.disabled:
		main_menu_button.grab_focus()
	else:
		next_level_button.grab_focus()


func _load_next_level() -> void:
	if _state != RunState.LEVEL_COMPLETE or next_level_scene == null:
		return
	get_tree().change_scene_to_packed(next_level_scene)


func _return_to_main_menu() -> void:
	get_tree().reload_current_scene()


func _restart_run() -> void:
	get_tree().reload_current_scene()


func _exit_run() -> void:
	if OS.has_feature("web"):
		get_tree().reload_current_scene()
	else:
		get_tree().quit()


func _restore_dancer() -> void:
	dancer.global_position = _checkpoint_position
	dancer.velocity = Vector3.ZERO
	dancer.set("has_fallen", false)
	dancer.set("in_balance_zone", false)
	dancer.set("in_low_transition", false)
	dancer.set("low_transition_timer", 0.0)
	dancer.set("pressing", false)
	dancer.set("hold_triggered", false)
	dancer.set("using_touch", false)
	dancer.set("active_touch_index", -1)
	if dancer.has_method("reset_locomotion_state"):
		dancer.call("reset_locomotion_state")

	var collider := dancer.get_node("CollisionShape3D") as CollisionShape3D
	var capsule := collider.shape as CapsuleShape3D
	if capsule != null:
		capsule.height = float(dancer.get("normal_collider_height"))
	collider.position.y = float(dancer.get("normal_collider_y"))
	var mesh := dancer.get_node("MeshInstance3D") as MeshInstance3D
	mesh.scale = dancer.get("normal_mesh_scale")
	mesh.position.y = float(dancer.get("normal_mesh_y"))


func _references_valid() -> bool:
	return (
		dancer != null
		and camera_rig != null
		and fork_camera_controller != null
		and start_gate != null
		and music_root != null
		and audio_player != null
		and flow_tracker != null
		and tap_timing_debug != null
		and accent_runtime_trace != null
		and game_over_overlay != null
		and continue_button != null
		and restart_button != null
		and exit_button != null
		and completion_trigger != null
		and level_complete_overlay != null
		and next_level_button != null
		and main_menu_button != null
		and next_level_status != null
		and checkpoint_status_label != null
	)
