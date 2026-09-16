extends Node

signal flow_state_changed(state: StringName, value: float)
signal flow_changed(value: float, delta: float, reason: String)

const FLOW_THRESHOLDS := {
	&"BUILDING": 0.05,
	&"FLOWING": 0.45,
	&"STRONG_FLOW": 0.75,
}

const CONTRIBUTIONS := {
	&"JUMP": 0.14,
	&"BALANCE": 0.14,
	&"SAFE_ROUTE": 0.08,
	&"TECHNICAL_ROUTE": 0.14,
	&"PERFECT": 0.16,
	&"GOOD": 0.11,
	&"EARLY": 0.04,
	&"LATE": 0.04,
}

const MISS_RETAINED_FRACTION := 0.60
const CONTINUITY_WINDOW_SECONDS := 8.0
const CONTINUITY_BONUS_PER_LINK := 0.02
const MAX_CONTINUITY_LINKS := 3
const MEANINGFUL_HOLD_SECONDS := 0.35
const DECAY_GRACE_SECONDS := 6.0
const DECAY_PER_SECOND := 0.01
const LANDING_MARGIN_X := 0.15
const LANDING_SEARCH_X := 6.0

@export var dancer: CharacterBody3D
@export var music_timeline: Node
@export var musicality: Node
@export var generated_level: Node3D
@export var debug_label: Label
@export_file("*.json") var geometry_plan_path := "res://data/geometry/graceful_opening.geometry_plan_v0_1.json"

var flow_value := 0.0
var _flow_state: StringName = &"EMPTY"
var _last_reason := "—"
var _last_playback_time := 0.0
var _last_success_time := -INF
var _continuity_links := 0
var _fall_was_active := false
var _balance_was_active := false
var _balance_hold_seconds := 0.0
var _jump_events: Array[Dictionary] = []
var _fork_events: Array[Dictionary] = []
var _miss_visible_through_process_frame := -1
var last_miss_before := 0.0
var last_miss_after := 0.0


func _ready() -> void:
	if dancer == null or music_timeline == null or musicality == null or generated_level == null:
		push_error("FlowTracker requires Dancer, MusicTimeline, Musicality, and GeneratedLevel references.")
		set_physics_process(false)
		return
	if not musicality.has_signal(&"accent_evaluated"):
		push_error("FlowTracker requires Musicality accent_evaluated signal.")
		set_physics_process(false)
		return
	musicality.connect(&"accent_evaluated", Callable(self, "_on_accent_evaluated"))
	if not _load_geometry_opportunities():
		set_physics_process(false)
		return
	_last_playback_time = _playback_time()
	_update_debug(0.0, "—")


func _physics_process(delta: float) -> void:
	var playback_time := _playback_time()
	if playback_time + 0.05 < _last_playback_time:
		_reset_flow("RESTART / SEEK")
		_reset_opportunities()
	_last_playback_time = playback_time

	var has_fallen := bool(dancer.get("has_fallen"))
	if has_fallen and not _fall_was_active:
		_reset_flow("SERIOUS INTERRUPTION: FALL")
	_fall_was_active = has_fallen
	if has_fallen:
		return
	# accent_evaluated is emitted synchronously from input handling. Without
	# this one-frame presentation guard, a landing/route outcome later in the
	# same rendered frame can replace the MISS value before the HUD is drawn.
	if Engine.get_process_frames() <= _miss_visible_through_process_frame:
		return

	_track_balance(delta, playback_time)
	_track_jump_events(playback_time)
	_track_forks(playback_time)
	_apply_gentle_decay(delta, playback_time)


func get_flow_state() -> StringName:
	if flow_value >= float(FLOW_THRESHOLDS[&"STRONG_FLOW"]):
		return &"STRONG_FLOW"
	if flow_value >= float(FLOW_THRESHOLDS[&"FLOWING"]):
		return &"FLOWING"
	if flow_value >= float(FLOW_THRESHOLDS[&"BUILDING"]):
		return &"BUILDING"
	return &"EMPTY"


func _load_geometry_opportunities() -> bool:
	var file := FileAccess.open(geometry_plan_path, FileAccess.READ)
	if file == null:
		push_error("FlowTracker could not open geometry plan: %s" % geometry_plan_path)
		return false
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		push_error("FlowTracker geometry plan is invalid.")
		return false
	var plan: Dictionary = parsed
	if not plan.has("events"):
		push_error("FlowTracker geometry plan has no events.")
		return false

	_jump_events.clear()
	_fork_events.clear()
	for source_event: Dictionary in plan["events"]:
		var movement_class := StringName(source_event["source_class"])
		var branch: Variant = source_event.get("branch")
		if branch != null:
			var technical_gap := _find_segment(branch["routes"]["technical"]["segments"], "MEDIUM_GAP")
			_fork_events.append({
				"source_time": float(source_event["source_time"]),
				"event_x": float(source_event["world"]["event_x"]),
				"split_x": float(branch["split"]["x"]),
				"merge_x": float(branch["merge"]["x"]),
				"safe_elevation": float(branch["routes"]["safe"]["elevation"]),
				"technical_elevation": float(branch["routes"]["technical"]["elevation"]),
				"gap_start_x": float(technical_gap["start_x"]),
				"gap_end_x": float(technical_gap["end_x"]),
				"route": &"",
				"gap_airborne": false,
				"gap_landed": false,
				"resolved": false,
			})
		elif String(movement_class).ends_with("_JUMP") or movement_class == &"LARGE_TRAVELLING_LEAP":
			var geometry: Dictionary = source_event["geometry"]
			_jump_events.append({
				"source_time": float(source_event["source_time"]),
				"movement_class": movement_class,
				"start_x": float(geometry["start_x"]),
				"end_x": float(geometry["end_x"]),
				"airborne": false,
				"resolved": false,
			})
	return true


func _find_segment(segments: Array, segment_type: String) -> Dictionary:
	for segment: Dictionary in segments:
		if String(segment["type"]) == segment_type:
			return segment
	return {}


func _track_balance(delta: float, playback_time: float) -> void:
	var active := bool(dancer.get("in_balance_zone"))
	if active:
		_balance_was_active = true
		if bool(dancer.get("pressing")) and bool(dancer.get("hold_triggered")):
			_balance_hold_seconds += delta
	elif _balance_was_active:
		if _balance_hold_seconds >= MEANINGFUL_HOLD_SECONDS:
			_apply_success(float(CONTRIBUTIONS[&"BALANCE"]), "BALANCE SUCCESS", playback_time)
		_balance_was_active = false
		_balance_hold_seconds = 0.0


func _track_jump_events(playback_time: float) -> void:
	var world_x := dancer.global_position.x
	var on_floor := dancer.is_on_floor()
	for event in _jump_events:
		if event["resolved"]:
			continue
		var start_x: float = event["start_x"]
		var end_x: float = event["end_x"]
		if world_x >= start_x - 1.0 and world_x <= end_x + LANDING_SEARCH_X and not on_floor:
			event["airborne"] = true
		if event["airborne"] and world_x >= end_x + LANDING_MARGIN_X and on_floor:
			event["resolved"] = true
			_apply_success(float(CONTRIBUTIONS[&"JUMP"]), "%s SUCCESS" % event["movement_class"], playback_time)
		elif world_x > end_x + LANDING_SEARCH_X:
			event["resolved"] = true


func _track_forks(playback_time: float) -> void:
	var world_x := dancer.global_position.x
	var world_y := dancer.global_position.y
	var on_floor := dancer.is_on_floor()
	for event in _fork_events:
		if event["resolved"] or world_x < float(event["split_x"]):
			continue
		if event["route"] == &"" and world_x <= float(event["merge_x"]):
			var route_threshold := lerpf(float(event["safe_elevation"]), float(event["technical_elevation"]), 0.5)
			if on_floor and world_y > route_threshold:
				event["route"] = &"TECHNICAL"
			elif on_floor and world_y <= route_threshold:
				event["route"] = &"SAFE"

		if event["route"] == &"TECHNICAL":
			if world_x >= float(event["gap_start_x"]) - 0.5 \
			and world_x <= float(event["gap_end_x"]) + LANDING_SEARCH_X \
			and not on_floor:
				event["gap_airborne"] = true
			if event["gap_airborne"] \
			and world_x >= float(event["gap_end_x"]) + LANDING_MARGIN_X \
			and on_floor \
			and world_y > lerpf(float(event["safe_elevation"]), float(event["technical_elevation"]), 0.5):
				event["gap_landed"] = true

		if world_x >= float(event["merge_x"]) + LANDING_MARGIN_X and on_floor:
			event["resolved"] = true
			if event["route"] == &"TECHNICAL" and event["gap_landed"]:
				_apply_success(float(CONTRIBUTIONS[&"TECHNICAL_ROUTE"]), "TECHNICAL ROUTE COMPLETE", playback_time)
			else:
				_apply_success(float(CONTRIBUTIONS[&"SAFE_ROUTE"]), "SAFE ROUTE COMPLETE", playback_time)
		elif world_x > float(event["merge_x"]) + LANDING_SEARCH_X:
			event["resolved"] = true


func _on_accent_evaluated(classification: StringName, delta: float, _marker_time: float) -> void:
	if classification == &"MISS":
		var previous := flow_value
		last_miss_before = previous
		last_miss_after = clampf(previous * MISS_RETAINED_FRACTION, 0.0, 1.0)
		_miss_visible_through_process_frame = Engine.get_process_frames() + 1
		var reason := "MISS ACCENT %.3f → %.3f" % [last_miss_before, last_miss_after]
		_set_flow(last_miss_after, reason)
		flow_changed.emit(flow_value, flow_value - previous, reason)
		return
	if not CONTRIBUTIONS.has(classification):
		return
	var direction := "" if classification in [&"PERFECT", &"GOOD"] else " (%+.2fs)" % delta
	_apply_success(float(CONTRIBUTIONS[classification]), "%s ACCENT%s" % [classification, direction], _playback_time())


func _apply_success(base_amount: float, reason: String, playback_time: float) -> void:
	if playback_time - _last_success_time <= CONTINUITY_WINDOW_SECONDS:
		_continuity_links = mini(_continuity_links + 1, MAX_CONTINUITY_LINKS)
	else:
		_continuity_links = 0
	var amount := base_amount + CONTINUITY_BONUS_PER_LINK * _continuity_links
	var previous := flow_value
	_set_flow(flow_value + amount, reason)
	_last_success_time = playback_time
	flow_changed.emit(flow_value, flow_value - previous, reason)


func _apply_gentle_decay(delta: float, playback_time: float) -> void:
	if _last_success_time == -INF or playback_time - _last_success_time <= DECAY_GRACE_SECONDS:
		return
	var previous := flow_value
	_set_flow(flow_value - DECAY_PER_SECOND * delta, "MUSICAL SPACE")
	if not is_equal_approx(previous, flow_value):
		flow_changed.emit(flow_value, flow_value - previous, "MUSICAL SPACE")


func _set_flow(value: float, reason: String) -> void:
	flow_value = clampf(value, 0.0, 1.0)
	_last_reason = reason
	var next_state := get_flow_state()
	if next_state != _flow_state:
		_flow_state = next_state
		flow_state_changed.emit(_flow_state, flow_value)
	_update_debug(flow_value, reason)


func _reset_flow(reason: String) -> void:
	_continuity_links = 0
	_last_success_time = -INF
	_balance_was_active = false
	_balance_hold_seconds = 0.0
	_miss_visible_through_process_frame = -1
	last_miss_before = 0.0
	last_miss_after = 0.0
	_set_flow(0.0, reason)


func _reset_opportunities() -> void:
	for event in _jump_events:
		event["airborne"] = false
		event["resolved"] = false
	for event in _fork_events:
		event["route"] = &""
		event["gap_airborne"] = false
		event["gap_landed"] = false
		event["resolved"] = false


func _playback_time() -> float:
	return float(music_timeline.call("get_playback_time"))


func _update_debug(_value: float, reason: String) -> void:
	if debug_label == null:
		return
	debug_label.text = "FLOW: %s %.2f\nLAST: %s" % [get_flow_state(), flow_value, reason]
