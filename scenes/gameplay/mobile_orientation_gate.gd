extends Node

@export var overlay: CanvasLayer
@export var audio_player: AudioStreamPlayer
@export var start_gate: Node

var _mobile_like := false
var _blocked := false
var _paused_by_orientation := false
var _resume_audio := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_mobile_like = OS.has_feature("mobile") or (
		OS.has_feature("web") and DisplayServer.is_touchscreen_available()
	)
	if overlay == null or audio_player == null or start_gate == null:
		push_error("MobileOrientationGate requires overlay, audio player, and start gate references.")
		return
	overlay.process_mode = Node.PROCESS_MODE_ALWAYS
	if start_gate.has_signal(&"runtime_started"):
		start_gate.connect(&"runtime_started", Callable(self, "_on_runtime_started"))
	get_viewport().size_changed.connect(_evaluate_orientation)
	_evaluate_orientation()


func _exit_tree() -> void:
	if _paused_by_orientation:
		get_tree().paused = false


func _evaluate_orientation() -> void:
	var viewport_size := get_viewport().get_visible_rect().size
	var should_block := _mobile_like and viewport_size.y > viewport_size.x
	if should_block == _blocked:
		return
	_blocked = should_block
	overlay.visible = _blocked
	if _blocked:
		_pause_for_portrait()
	else:
		_resume_from_portrait()


func _pause_for_portrait() -> void:
	_resume_audio = audio_player.playing and not audio_player.stream_paused
	if _resume_audio:
		audio_player.stream_paused = true
	if not get_tree().paused:
		get_tree().paused = true
		_paused_by_orientation = true


func _resume_from_portrait() -> void:
	if _paused_by_orientation:
		get_tree().paused = false
		_paused_by_orientation = false
	if _resume_audio and audio_player.playing:
		audio_player.stream_paused = false
	_resume_audio = false


func _on_runtime_started() -> void:
	if OS.has_feature("web"):
		_request_web_landscape()


func _request_web_landscape() -> void:
	JavaScriptBridge.eval(
		"if (screen.orientation && screen.orientation.lock) { screen.orientation.lock('landscape').catch(function(){}); }",
		true
	)
