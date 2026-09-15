extends Node3D

@export var target: Node3D
@export var follow_speed: float = 8.0
@export var look_ahead: float = 1.5

func _process(delta: float) -> void:
	if target == null:
		return

	var desired_x := target.global_position.x + look_ahead
	global_position.x = lerpf(
		global_position.x,
		desired_x,
		1.0 - exp(-follow_speed * delta)
	)
