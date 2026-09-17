extends CanvasLayer

@export var hud_root: Control
@export var start_gate: Node

# Presentation-only compatibility filter for debug labels in Web/mobile builds.
# Code points keep the source itself ASCII-safe while preserving gameplay sources.
const ASCII_REPLACEMENTS := {
	0x2014: "-",  # em dash
	0x2190: "<-", # left arrow
	0x2191: "UP", # up arrow
	0x2192: "->", # right arrow
	0x2193: "DOWN", # down arrow
	0x2500: "-",  # box drawing light horizontal
	0x2502: "|",  # box drawing light vertical
	0x2501: "=",  # box drawing heavy horizontal
	0x2550: "#",  # box drawing double horizontal
	0x25CF: "o",  # black circle
}


func _ready() -> void:
	process_priority = 1000
	set_process_input(false)
	if hud_root == null or start_gate == null or not start_gate.has_signal("runtime_started"):
		push_error("DebugHUD requires HUDRoot and RuntimeStartGate references.")
		return
	hud_root.visible = false
	start_gate.connect("runtime_started", Callable(self, "_on_runtime_started"))
	_sanitize_labels(self)


func _on_runtime_started() -> void:
	set_process_input(true)


func _input(event: InputEvent) -> void:
	if not event is InputEventKey:
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo or key_event.keycode != KEY_H:
		return
	get_viewport().set_input_as_handled()
	hud_root.visible = not hud_root.visible


func _process(_delta: float) -> void:
	_sanitize_labels(self)


func _sanitize_labels(node: Node) -> void:
	for child in node.get_children():
		if child is Label:
			var label := child as Label
			var safe_text := label.text
			for codepoint: int in ASCII_REPLACEMENTS:
				safe_text = safe_text.replace(
					String.chr(codepoint),
					String(ASCII_REPLACEMENTS[codepoint])
				)
			if safe_text != label.text:
				label.text = safe_text
		_sanitize_labels(child)
