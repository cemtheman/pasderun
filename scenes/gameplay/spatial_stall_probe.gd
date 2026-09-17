extends Node

@export var start_gate: Node
@export var fork_camera_framing: Node
@export var fork_debug_visualization: Node3D
@export var parallax_presentation: Node3D
@export var debug_label: Label

const VISUALIZATION_MODE_COUNT := 5
const VISUALIZATION_MODE_ALL := 4

var _framing_enabled := true
var _visualization_mode := VISUALIZATION_MODE_ALL
var _background_enabled := true


func _ready() -> void:
	set_process_input(false)
	if (
		start_gate == null
		or fork_camera_framing == null
		or fork_debug_visualization == null
		or parallax_presentation == null
		or debug_label == null
		or not start_gate.has_signal("runtime_started")
		or not fork_debug_visualization.has_method("set_diagnostic_mode")
		or not fork_debug_visualization.has_method("get_diagnostic_mode_name")
	):
		push_error("SpatialStallProbe requires start gate, fork helpers, and debug label.")
		return

	start_gate.connect("runtime_started", Callable(self, "_on_runtime_started"))
	_update_debug_label()


func _on_runtime_started() -> void:
	set_process_input(true)


func _input(event: InputEvent) -> void:
	if not event is InputEventKey:
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return

	if key_event.keycode == KEY_F:
		get_viewport().set_input_as_handled()
		_set_framing_enabled(not _framing_enabled)
	elif key_event.keycode == KEY_V:
		get_viewport().set_input_as_handled()
		_cycle_visualization_mode()
	elif key_event.keycode == KEY_B:
		get_viewport().set_input_as_handled()
		_set_background_enabled(not _background_enabled)


func _set_framing_enabled(enabled: bool) -> void:
	_framing_enabled = enabled
	fork_camera_framing.process_mode = (
		Node.PROCESS_MODE_INHERIT if enabled else Node.PROCESS_MODE_DISABLED
	)
	_update_debug_label()


func _cycle_visualization_mode() -> void:
	_visualization_mode = (
		(_visualization_mode + 1) % VISUALIZATION_MODE_COUNT
	)
	fork_debug_visualization.call("set_diagnostic_mode", _visualization_mode)
	_update_debug_label()


func _set_background_enabled(enabled: bool) -> void:
	_background_enabled = enabled
	parallax_presentation.visible = enabled
	_update_debug_label()


func _update_debug_label() -> void:
	debug_label.text = "STALL PROBE FRAMING:%s VISUALS:%s BG:%s" % [
		"ON" if _framing_enabled else "OFF",
		String(fork_debug_visualization.call("get_diagnostic_mode_name")),
		"ON" if _background_enabled else "OFF",
	]
