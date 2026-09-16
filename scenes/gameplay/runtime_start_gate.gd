extends Node

signal runtime_started

@export var dancer: CharacterBody3D
@export var music_root: Node
@export var audio_player: AudioStreamPlayer
@export var flow_tracker: Node
@export var tap_timing_debug: Node
@export var accent_runtime_trace: Node
@export var overlay: CanvasLayer

var _started := false


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
		set_process_input(false)
		return

	audio_player.stop()
	music_root.process_mode = Node.PROCESS_MODE_DISABLED
	dancer.process_mode = Node.PROCESS_MODE_DISABLED
	flow_tracker.process_mode = Node.PROCESS_MODE_DISABLED
	tap_timing_debug.process_mode = Node.PROCESS_MODE_DISABLED
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_DISABLED
	overlay.visible = true


func _input(event: InputEvent) -> void:
	if _started or not _is_valid_start_event(event):
		return

	_started = true
	get_viewport().set_input_as_handled()

	# Web audio must be unlocked synchronously inside the user gesture.
	music_root.process_mode = Node.PROCESS_MODE_INHERIT
	flow_tracker.process_mode = Node.PROCESS_MODE_INHERIT
	tap_timing_debug.process_mode = Node.PROCESS_MODE_INHERIT
	accent_runtime_trace.process_mode = Node.PROCESS_MODE_INHERIT
	audio_player.play(0.0)
	overlay.visible = false

	# Dancer stays disabled until this input event has fully left the tree, so
	# the start gesture cannot also become a Tap, jump, hold, or swipe.
	call_deferred("_enable_dancer_after_start_input")


func _enable_dancer_after_start_input() -> void:
	dancer.process_mode = Node.PROCESS_MODE_INHERIT
	runtime_started.emit()
	set_process_input(false)


func _is_valid_start_event(event: InputEvent) -> bool:
	if event is InputEventScreenTouch:
		return event.pressed
	if event is InputEventMouseButton:
		return event.pressed and event.button_index == MOUSE_BUTTON_LEFT
	if event is InputEventKey:
		return event.pressed and not event.echo
	return false
