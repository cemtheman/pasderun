extends Node

const DEATH_Y := -6.0
const RUN_SPEED := 4.0
const CHECKPOINT_SURFACE_Y := -2.8
const DANCER_STANDING_OFFSET := 1.5

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

var _dead := false
var _checkpoint_index := 0
var _checkpoint_position := Vector3.ZERO
var _checkpoint_music_time := 0.0


func _ready() -> void:
	if not _references_valid():
		push_error("RunRecoveryManager requires all runtime and Game Over references.")
		set_physics_process(false)
		return
	_checkpoint_position = dancer.global_position
	game_over_overlay.visible = false
	continue_button.pressed.connect(_continue_from_checkpoint)
	restart_button.pressed.connect(_restart_run)
	exit_button.pressed.connect(_exit_run)


func _physics_process(_delta: float) -> void:
	if _dead or not audio_player.playing:
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
	_checkpoint_position = Vector3(
		float(candidate["x"]),
		CHECKPOINT_SURFACE_Y + DANCER_STANDING_OFFSET,
		0.0
	)
	_checkpoint_music_time = float(candidate["x"]) / RUN_SPEED


func _enter_dead_state() -> void:
	_dead = true
	fork_camera_controller.call("set_frozen", true)
	camera_rig.process_mode = Node.PROCESS_MODE_DISABLED
	dancer.process_mode = Node.PROCESS_MODE_DISABLED
	audio_player.stop()
	music_root.process_mode = Node.PROCESS_MODE_DISABLED
	flow_tracker.process_mode = Node.PROCESS_MODE_DISABLED
	tap_timing_debug.process_mode = Node.PROCESS_MODE_DISABLED
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_DISABLED
	game_over_overlay.visible = true
	continue_button.grab_focus()


func _continue_from_checkpoint() -> void:
	if not _dead or not continue_is_allowed():
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
	_dead = false


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
	)
