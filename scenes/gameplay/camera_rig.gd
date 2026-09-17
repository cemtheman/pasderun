extends Node3D

@export var target: Node3D
@export var follow_speed: float = 8.0
@export var vertical_follow_speed: float = 6.0
@export var look_ahead: float = 1.75

var _vertical_offset: float = 0.0


func _ready() -> void:
	if target != null:
		_vertical_offset = global_position.y - target.global_position.y


func _process(delta: float) -> void:
	if target == null:
		return

	var desired_x := target.global_position.x + look_ahead
	global_position.x = lerpf(
		global_position.x,
		desired_x,
		1.0 - exp(-follow_speed * delta)
	)

	var desired_y := target.global_position.y + _vertical_offset
	global_position.y = lerpf(
		global_position.y,
		desired_y,
		1.0 - exp(-vertical_follow_speed * delta)
	)


func reset_to_target() -> void:
	if target == null:
		return
	global_position.x = target.global_position.x + look_ahead
	global_position.y = target.global_position.y + _vertical_offset
