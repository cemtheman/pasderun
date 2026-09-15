extends Node

const ACCENT_MARKERS: Array[float] = [18.0, 22.0, 26.0]
const PERFECT_WINDOW := 0.12
const GOOD_WINDOW := 0.28
const EARLY_LATE_WINDOW := 0.50
const FEEDBACK_DURATION := 1.5

@export var music_timeline: Node
@export var dancer: Node
@export var debug_label: Label

var _consumed_accents: Dictionary = {}
var _last_playback_time := 0.0
var _feedback_remaining := 0.0


func _ready() -> void:
	if music_timeline == null or dancer == null:
		push_error("Musicality requires MusicTimeline and Dancer references.")
		set_process(false)
		return
	if not dancer.has_signal(&"tap_detected"):
		push_error("Musicality requires the existing Dancer tap_detected signal.")
		set_process(false)
		return
	dancer.connect(&"tap_detected", Callable(self, "_on_tap_detected"))
	_last_playback_time = _playback_time()


func _process(delta: float) -> void:
	var playback_time := _playback_time()
	if playback_time + 0.05 < _last_playback_time:
		_consumed_accents.clear()
	_last_playback_time = playback_time

	if _feedback_remaining > 0.0:
		_feedback_remaining -= delta
		if _feedback_remaining <= 0.0 and debug_label != null:
			debug_label.text = "ACCENT: —"


func _on_tap_detected() -> void:
	var playback_time := _playback_time()
	var accent_index := _nearest_available_accent(playback_time)
	if accent_index < 0:
		_show_feedback("MISS")
		return

	var delta := playback_time - ACCENT_MARKERS[accent_index]
	var absolute_delta := absf(delta)
	if absolute_delta > EARLY_LATE_WINDOW:
		_show_feedback("MISS")
		return

	_consumed_accents[accent_index] = true
	var classification := _classify_delta(delta)
	var sign := "+" if delta >= 0.0 else ""
	_show_feedback("%s  (%s%.2fs)" % [classification, sign, delta])


func _nearest_available_accent(playback_time: float) -> int:
	var nearest_index := -1
	var nearest_distance := INF
	for index in ACCENT_MARKERS.size():
		if _consumed_accents.has(index):
			continue
		var distance := absf(playback_time - ACCENT_MARKERS[index])
		if distance < nearest_distance:
			nearest_distance = distance
			nearest_index = index
	return nearest_index


func _classify_delta(delta: float) -> StringName:
	var absolute_delta := absf(delta)
	if absolute_delta <= PERFECT_WINDOW:
		return &"PERFECT"
	if absolute_delta <= GOOD_WINDOW:
		return &"GOOD"
	return &"EARLY" if delta < 0.0 else &"LATE"


func _playback_time() -> float:
	return float(music_timeline.call("get_playback_time"))


func _show_feedback(message: String) -> void:
	if debug_label != null:
		debug_label.text = "ACCENT: %s" % message
	_feedback_remaining = FEEDBACK_DURATION
