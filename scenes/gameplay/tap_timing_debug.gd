extends Node

const INDICATOR_WIDTH := 29

@export var musicality: Node
@export var music_timeline: Node
@export var debug_label: Label

var _last_playback_time := 0.0
var _last_classification := "-"


func _ready() -> void:
	process_priority = 10
	if musicality == null or music_timeline == null or debug_label == null:
		push_error("TapTimingDebug requires Musicality, MusicTimeline, and DebugLabel references.")
		set_process(false)
		return
	if not musicality.has_signal(&"accent_evaluated"):
		push_error("TapTimingDebug requires Musicality accent_evaluated signal.")
		set_process(false)
		return
	musicality.connect(&"accent_evaluated", Callable(self, "_on_accent_evaluated"))
	_last_playback_time = _playback_time()
	if debug_label.is_visible_in_tree():
		_update_cue(_last_playback_time)


func _process(_delta: float) -> void:
	var playback_time := _playback_time()
	if not debug_label.is_visible_in_tree():
		_last_playback_time = playback_time
		return
	if playback_time + 0.05 < _last_playback_time:
		_last_classification = "-"
	_last_playback_time = playback_time
	_update_cue(playback_time)


func _update_cue(playback_time: float) -> void:
	var opportunity: Dictionary = musicality.call("get_next_accent_opportunity", playback_time)
	if opportunity.is_empty():
		debug_label.text = "NEXT TAP: -\nNO UPCOMING TAP OPPORTUNITY\nLAST ACCENT: %s" % _last_classification
		return

	var windows: Dictionary = musicality.call("get_timing_windows")
	var marker_time := float(opportunity["time"])
	var delta := playback_time - marker_time
	var seconds_until := marker_time - playback_time
	var absolute_delta := absf(delta)
	var cue_state := "APPROACH"
	if absolute_delta <= float(windows["early_late"]):
		cue_state = ">>> TAP NOW - %s <<<" % _window_region(delta, windows)

	debug_label.text = "NEXT TAP: %+.2fs\n%s\n%s\nLAST ACCENT: %s" % [
		seconds_until,
		cue_state,
		_timing_indicator(delta, windows),
		_last_classification,
	]


func _window_region(delta: float, windows: Dictionary) -> String:
	var absolute_delta := absf(delta)
	if absolute_delta <= float(windows["perfect"]):
		return "PERFECT"
	if absolute_delta <= float(windows["good"]):
		return "GOOD"
	return "EARLY" if delta < 0.0 else "LATE"


func _timing_indicator(delta: float, windows: Dictionary) -> String:
	var outer_window := float(windows["early_late"])
	var perfect_window := float(windows["perfect"])
	var good_window := float(windows["good"])
	var marker_position := roundi(
		clampf((delta + outer_window) / (outer_window * 2.0), 0.0, 1.0)
		* float(INDICATOR_WIDTH - 1)
	)
	var center := (INDICATOR_WIDTH - 1) / 2
	var characters := PackedStringArray()
	for index in INDICATOR_WIDTH:
		var sample_delta := lerpf(
			-outer_window,
			outer_window,
			float(index) / float(INDICATOR_WIDTH - 1)
		)
		var distance := absf(sample_delta)
		var character := "-"
		if distance <= good_window:
			character = "="
		if distance <= perfect_window:
			character = "#"
		if index == center:
			character = "|"
		if index == marker_position:
			character = "o"
		characters.append(character)
	return "EARLY      PERFECT      LATE\n%s" % "".join(characters)


func _on_accent_evaluated(classification: StringName, delta: float, marker_time: float) -> void:
	if classification == &"MISS":
		_last_classification = "MISS"
	elif marker_time >= 0.0:
		_last_classification = "%s (%+.2fs)" % [classification, delta]


func _playback_time() -> float:
	return float(music_timeline.call("get_playback_time"))
