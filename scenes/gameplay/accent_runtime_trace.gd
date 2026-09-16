extends Node

@export var musicality: Node
@export var flow_tracker: Node
@export var flow_debug_label: Label
@export var trace_label: Label

var _trace_serial := 0
var _tap_time := 0.0
var _marker_time := -1.0
var _tap_delta := 0.0
var _input_source := &"NONE"
var _classification := &"PENDING"
var _signal_status := "PENDING"
var _flow_before := 0.0
var _flow_handler := 0.0
var _flow_next_physics := 0.0
var _hud_flow := 0.0
var _handler_captured := false
var _next_physics_captured := false
var _awaiting_next_physics := false
var _handler_physics_frame := -1


func _ready() -> void:
	process_physics_priority = 100
	if musicality == null or flow_tracker == null or flow_debug_label == null or trace_label == null:
		push_error("AccentRuntimeTrace requires Musicality, FlowTracker, FlowDebug, and TraceLabel references.")
		set_physics_process(false)
		return
	if not musicality.has_signal(&"accent_evaluation_started") \
	or not musicality.has_signal(&"accent_evaluated") \
	or not flow_tracker.has_signal(&"flow_changed"):
		push_error("AccentRuntimeTrace requires the existing Musicality and FlowTracker diagnostic signals.")
		set_physics_process(false)
		return
	musicality.connect(&"accent_evaluation_started", Callable(self, "_on_accent_evaluation_started"))
	musicality.connect(&"accent_evaluated", Callable(self, "_on_accent_evaluated"))
	flow_tracker.connect(&"flow_changed", Callable(self, "_on_flow_changed"))
	_update_trace()


func _physics_process(_delta: float) -> void:
	if not _awaiting_next_physics:
		return
	if Engine.get_physics_frames() <= _handler_physics_frame:
		return
	_flow_next_physics = _current_flow()
	_hud_flow = _read_hud_flow()
	_next_physics_captured = true
	_awaiting_next_physics = false
	_update_trace()
	print("ACCENT RUNTIME TRACE\n", trace_label.text)


func _on_accent_evaluation_started(
	playback_time: float,
	marker_time: float,
	delta: float,
	input_source: StringName
) -> void:
	_trace_serial += 1
	_tap_time = playback_time
	_marker_time = marker_time
	_tap_delta = delta
	_input_source = input_source
	_classification = &"PENDING"
	_signal_status = "PENDING"
	_flow_before = _current_flow()
	_flow_handler = _flow_before
	_flow_next_physics = _flow_before
	_hud_flow = _read_hud_flow()
	_handler_captured = false
	_next_physics_captured = false
	_awaiting_next_physics = false
	_update_trace()
	call_deferred("_confirm_signal_presence", _trace_serial)


func _on_flow_changed(value: float, _delta: float, reason: String) -> void:
	if _signal_status != "PENDING" or not reason.contains("ACCENT"):
		return
	_flow_handler = value
	_hud_flow = _read_hud_flow()
	_handler_captured = true


func _on_accent_evaluated(classification: StringName, _delta: float, _marker_time_value: float) -> void:
	_classification = classification
	_signal_status = "YES"
	if not _handler_captured:
		_flow_handler = _current_flow()
		_hud_flow = _read_hud_flow()
		_handler_captured = true
	_handler_physics_frame = Engine.get_physics_frames()
	_awaiting_next_physics = true
	_update_trace()


func _confirm_signal_presence(serial: int) -> void:
	if serial != _trace_serial or _signal_status != "PENDING":
		return
	_signal_status = "NO"
	_flow_handler = _current_flow()
	_hud_flow = _read_hud_flow()
	_handler_captured = true
	_update_trace()
	print("ACCENT RUNTIME TRACE\n", trace_label.text)


func _current_flow() -> float:
	return float(flow_tracker.get("flow_value"))


func _read_hud_flow() -> float:
	var first_line := flow_debug_label.text.get_slice("\n", 0)
	var fields := first_line.split(" ", false)
	if fields.size() < 3:
		return _current_flow()
	return float(fields[2])


func _update_trace() -> void:
	var marker_text := "NONE" if _marker_time < 0.0 else "%.3f" % _marker_time
	var handler_text := "-" if not _handler_captured else "%.3f" % _flow_handler
	var next_text := "-" if not _next_physics_captured else "%.3f" % _flow_next_physics
	trace_label.text = (
		"EVAL t=%.3f\n"
		+ "MARKER=%s\n"
		+ "DELTA=%+.3f\n"
		+ "INPUT=%s\n"
		+ "CLASS=%s\n"
		+ "SIGNAL=%s\n"
		+ "FLOW BEFORE=%.3f\n"
		+ "FLOW HANDLER=%s\n"
		+ "FLOW NEXT PHYSICS=%s\n"
		+ "HUD FLOW=%.3f"
	) % [
		_tap_time,
		marker_text,
		_tap_delta,
		_input_source,
		_classification,
		_signal_status,
		_flow_before,
		handler_text,
		next_text,
		_hud_flow,
	]
