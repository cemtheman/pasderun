extends Node

@export var camera_rig: Node3D
@export var camera: Camera3D
@export var target: Node3D
@export var generated_level: Node3D
@export var approach_distance: float = 6.0
@export var exit_distance: float = 4.0
@export var vertical_padding: float = 0.4

var _default_camera_size: float = 5.5
var _forks: Array[Dictionary] = []
var _frozen := false


func _ready() -> void:
	process_priority = 10
	if camera != null:
		_default_camera_size = camera.size
	_collect_forks()


func _process(_delta: float) -> void:
	if _frozen or camera_rig == null or camera == null or target == null:
		return

	var active_fork := _find_active_fork(target.global_position.x)
	if active_fork.is_empty():
		camera.size = _default_camera_size
		return

	var weight := _framing_weight(active_fork, target.global_position.x)
	var min_y: float = active_fork["min_y"]
	var max_y: float = active_fork["max_y"]
	var framed_center_y := (min_y + max_y) * 0.5
	var framed_size := maxf(
		_default_camera_size,
		max_y - min_y + vertical_padding * 2.0
	)

	# camera_rig.gd önce normal dancer-follow konumunu üretir. Bu helper
	# yalnız fork bölgesinde o sonucu iki rotanın ortak kadrajına doğru blend eder.
	var framed_rig_y := framed_center_y - camera.position.y
	camera_rig.global_position.y = lerpf(
		camera_rig.global_position.y,
		framed_rig_y,
		weight
	)
	camera.size = lerpf(_default_camera_size, framed_size, weight)


func set_frozen(value: bool) -> void:
	_frozen = value


func restore_normal_state() -> void:
	_frozen = false
	if camera != null:
		camera.size = _default_camera_size


func is_outside_fork() -> bool:
	if target == null:
		return true
	var world_x := target.global_position.x
	for fork in _forks:
		if world_x >= float(fork["start_x"]) and world_x <= float(fork["merge_x"]):
			return false
	return true


func _collect_forks() -> void:
	_forks.clear()
	if generated_level == null:
		return

	var level := generated_level.get_node_or_null("Level")
	if level == null:
		return

	for child in level.get_children():
		if not String(child.name).begins_with("SafeLowerRoute"):
			continue

		var suffix := String(child.name).trim_prefix("SafeLowerRoute")
		var fork_start := level.get_node_or_null("ForkStart" + suffix) as Marker3D
		var fork_merge := level.get_node_or_null("ForkMerge" + suffix) as Marker3D
		var safe_body := child as StaticBody3D
		if fork_start == null or fork_merge == null or safe_body == null:
			continue

		var safe_bounds := _body_vertical_bounds(safe_body)
		var technical_top := -INF
		for candidate in level.get_children():
			if String(candidate.name).begins_with("TechnicalRoute" + suffix + "_"):
				var bounds := _body_vertical_bounds(candidate as StaticBody3D)
				technical_top = maxf(technical_top, bounds.y)

		if technical_top == -INF:
			continue

		var target_height := _target_height()
		_forks.append({
			"start_x": fork_start.global_position.x,
			"merge_x": fork_merge.global_position.x,
			"min_y": safe_bounds.x,
			"max_y": technical_top + target_height,
		})


func _body_vertical_bounds(body: StaticBody3D) -> Vector2:
	if body == null:
		return Vector2.ZERO
	var collider := body.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if collider == null or not collider.shape is BoxShape3D:
		return Vector2(body.global_position.y, body.global_position.y)
	var box := collider.shape as BoxShape3D
	var half_height := box.size.y * 0.5
	return Vector2(
		collider.global_position.y - half_height,
		collider.global_position.y + half_height
	)


func _target_height() -> float:
	if target == null:
		return 2.0
	var collider := target.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if collider != null and collider.shape is CapsuleShape3D:
		return (collider.shape as CapsuleShape3D).height
	return 2.0


func _find_active_fork(world_x: float) -> Dictionary:
	for fork in _forks:
		if world_x >= fork["start_x"] - approach_distance \
		and world_x <= fork["merge_x"] + exit_distance:
			return fork
	return {}


func _framing_weight(fork: Dictionary, world_x: float) -> float:
	var start_x: float = fork["start_x"]
	var merge_x: float = fork["merge_x"]
	if world_x < start_x:
		return smoothstep(start_x - approach_distance, start_x, world_x)
	if world_x > merge_x:
		return 1.0 - smoothstep(merge_x, merge_x + exit_distance, world_x)
	return 1.0
