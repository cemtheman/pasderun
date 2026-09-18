extends Node

@export var pause_button: Button
@export var pause_overlay: Control
@export var resume_button: Button
@export var start_gate: Node
@export var recovery_manager: Node
@export var audio_player: AudioStreamPlayer

var _runtime_started := false
var _paused_by_user := false
var _paused_audio_position := 0.0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if (
		pause_button == null
		or pause_overlay == null
		or resume_button == null
		or start_gate == null
		or recovery_manager == null
		or audio_player == null
	):
		push_error("PauseController requires UI, start gate, recovery manager and audio.")
		set_process(false)
		set_process_input(false)
		return

	pause_button.visible = false
	pause_overlay.visible = false
	pause_button.focus_mode = Control.FOCUS_NONE
	resume_button.focus_mode = Control.FOCUS_NONE
	pause_button.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
	resume_button.action_mode = BaseButton.ACTION_MODE_BUTTON_PRESS
	pause_button.release_focus()
	resume_button.release_focus()
	pause_button.pressed.connect(_toggle_pause)
	resume_button.pressed.connect(_toggle_pause)
	start_gate.connect("runtime_started", Callable(self, "_on_runtime_started"))


func _process(_delta: float) -> void:
	if not _runtime_started or _paused_by_user:
		return
	pause_button.visible = (
		recovery_manager.has_method("get_run_state")
		and String(recovery_manager.call("get_run_state")) == "PLAYING"
	)


func _input(event: InputEvent) -> void:
	if not _runtime_started:
		return
	if not event is InputEventKey:
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return
	if key_event.keycode != KEY_P and key_event.keycode != KEY_ESCAPE:
		return
	if not _can_toggle():
		return
	get_viewport().set_input_as_handled()
	_toggle_pause()


func _on_runtime_started() -> void:
	_runtime_started = true
	pause_button.visible = true


func _can_toggle() -> bool:
	if _paused_by_user:
		return true
	return (
		recovery_manager.has_method("get_run_state")
		and String(recovery_manager.call("get_run_state")) == "PLAYING"
	)


func _toggle_pause() -> void:
	pause_button.release_focus()
	resume_button.release_focus()
	if not _can_toggle():
		return
	_set_paused(not _paused_by_user)


func _set_paused(paused: bool) -> void:
	_paused_by_user = paused
	pause_overlay.visible = paused
	pause_button.text = ">" if paused else "II"
	pause_button.release_focus()
	resume_button.release_focus()

	if paused:
		_paused_audio_position = audio_player.get_playback_position()
		audio_player.stream_paused = true
		get_tree().paused = true
		return

	# Web MP3 playback may resume from 0 after stream_paused is cleared.
	# Restore the exact captured playback position explicitly, matching the
	# orientation-gate resume contract. Restore audio before releasing the
	# scene tree so gameplay cannot advance ahead of the resumed soundtrack.
	if audio_player.playing:
		audio_player.stream_paused = false
		audio_player.seek(_paused_audio_position)
	else:
		audio_player.play(_paused_audio_position)
	get_tree().paused = false


func _exit_tree() -> void:
	if _paused_by_user:
		get_tree().paused = false
		if is_instance_valid(audio_player):
			audio_player.stream_paused = false
