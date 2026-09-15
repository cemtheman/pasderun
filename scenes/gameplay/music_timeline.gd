extends Node

signal marker_crossed(section: StringName, playback_time: float)

const MARKERS: Array[Dictionary] = [
	{"time": 0.0, "section": &"OPENING", "phrase": &"OPENING"},
	{"time": 15.0, "section": &"RHYTHM", "phrase": &"RHYTHM"},
	{"time": 30.0, "section": &"CONNECTION", "phrase": &"CONNECTION"},
	{"time": 45.0, "section": &"TECHNICAL_01", "phrase": &"TECHNICAL_01"},
	{"time": 60.0, "section": &"END_OF_PROTOTYPE_BLOCK", "phrase": &"END_OF_PROTOTYPE_BLOCK"},
]

@export var audio_player: AudioStreamPlayer
@export var debug_label: Label

var _last_playback_time := -0.001
var _crossed_markers: Dictionary = {}


func _ready() -> void:
	if audio_player == null:
		push_error("MusicTimeline requires an AudioStreamPlayer.")
		set_process(false)
		return

	if audio_player.stream is AudioStreamMP3:
		var mp3_stream := audio_player.stream as AudioStreamMP3
		mp3_stream.loop = false
	_update_debug(audio_player.get_playback_position())


func _process(_delta: float) -> void:
	var playback_time := audio_player.get_playback_position()

	if playback_time + 0.05 < _last_playback_time:
		_rebuild_marker_state(playback_time)

	_emit_crossed_markers(_last_playback_time, playback_time)
	_last_playback_time = playback_time
	_update_debug(playback_time)


func get_playback_time() -> float:
	return audio_player.get_playback_position() if audio_player != null else 0.0


func get_current_section(playback_time: float = -1.0) -> StringName:
	return _current_marker_value(&"section", playback_time)


func get_current_phrase(playback_time: float = -1.0) -> StringName:
	return _current_marker_value(&"phrase", playback_time)


func _current_marker_value(key: StringName, playback_time: float) -> StringName:
	var time := get_playback_time() if playback_time < 0.0 else playback_time
	var value: StringName = MARKERS[0][key]
	for marker in MARKERS:
		if time < float(marker["time"]):
			break
		value = marker[key]
	return value


func _emit_crossed_markers(previous_time: float, playback_time: float) -> void:
	for index in MARKERS.size():
		var marker := MARKERS[index]
		var marker_time := float(marker["time"])
		if not _crossed_markers.has(index) and previous_time < marker_time and playback_time >= marker_time:
			_crossed_markers[index] = true
			var section: StringName = marker["section"]
			marker_crossed.emit(section, playback_time)
			print("SECTION: %s" % section)


func _rebuild_marker_state(playback_time: float) -> void:
	_crossed_markers.clear()
	for index in MARKERS.size():
		if float(MARKERS[index]["time"]) < playback_time:
			_crossed_markers[index] = true
	_last_playback_time = playback_time - 0.001


func _update_debug(playback_time: float) -> void:
	if debug_label == null:
		return
	var duration := audio_player.stream.get_length() if audio_player.stream != null else 0.0
	debug_label.text = "MUSIC: %s / %s\nSECTION: %s" % [
		_format_time(playback_time, true),
		_format_time(duration, true),
		get_current_section(playback_time),
	]


func _format_time(seconds: float, show_tenths: bool) -> String:
	var minutes := int(seconds) / 60
	var whole_seconds := int(seconds) % 60
	if show_tenths:
		var tenths := int(fmod(seconds, 1.0) * 10.0)
		return "%02d:%02d.%d" % [minutes, whole_seconds, tenths]
	return "%02d:%02d" % [minutes, whole_seconds]
