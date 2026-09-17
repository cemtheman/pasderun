extends Node

const NORMAL_CAMERA_SIZE := 7.5
const NORMAL_LOOK_AHEAD := 1.75
const TRANSITION_SPEED := 4.5

@export var camera_rig: Node3D
@export var camera: Camera3D
@export var target: Node3D
@export var course_root: Node3D

var _forks: Array[Dictionary] = []
var _active_index := -1
var _state := "OUTSIDE"
var _frozen := false


func _ready() -> void:
	process_priority = 20
	_collect_fork_metadata()


func _process(delta: float) -> void:
	if _frozen or camera_rig == null or camera == null or target == null:
		return

	var world_x := target.global_position.x
	if _active_index < 0:
		_active_index = _fork_index_containing(world_x)

	var target_size := NORMAL_CAMERA_SIZE
	var target_look_ahead := NORMAL_LOOK_AHEAD
	var fork_rig_y := camera_rig.global_position.y
	var frame_fork_vertically := false
	if _active_index >= 0:
		var fork := _forks[_active_index]
		if world_x >= float(fork["end_x"]):
			_active_index = -1
			_state = "OUTSIDE"
		else:
			var route_height := (
				float(fork["upper_max_y"])
				+ 2.0
				- float(fork["lower_min_y"])
			)
			var required_vertical_size := route_height + float(fork["camera_margin"]) * 2.0
			target_size = maxf(float(fork["target_camera_size"]), required_vertical_size)
			target_look_ahead = float(fork["target_look_ahead"])
			var route_center_y := (
				float(fork["lower_min_y"])
				+ float(fork["upper_max_y"])
				+ 2.0
			) * 0.5
			fork_rig_y = route_center_y - camera.position.y
			frame_fork_vertically = true
			_state = _state_for_position(fork, world_x)

	var blend := 1.0 - exp(-TRANSITION_SPEED * delta)
	camera.size = lerpf(camera.size, target_size, blend)
	camera_rig.set("look_ahead", lerpf(float(camera_rig.get("look_ahead")), target_look_ahead, blend))
	if frame_fork_vertically:
		camera_rig.global_position.y = lerpf(camera_rig.global_position.y, fork_rig_y, blend)


func set_frozen(value: bool) -> void:
	_frozen = value


func restore_normal_state() -> void:
	_active_index = -1
	_state = "OUTSIDE"
	_frozen = false
	if camera != null:
		camera.size = NORMAL_CAMERA_SIZE
	if camera_rig != null:
		camera_rig.set("look_ahead", NORMAL_LOOK_AHEAD)


func get_fork_state() -> String:
	return _state


func get_active_fork_id() -> int:
	if _active_index < 0:
		return 0
	return int(_forks[_active_index]["fork_id"])


func is_outside_fork() -> bool:
	return _active_index < 0


func _collect_fork_metadata() -> void:
	_forks.clear()
	if course_root == null:
		return
	var level := course_root.get_node_or_null("Level")
	if level == null:
		return

	for child in level.get_children():
		if not String(child.name).begins_with("RouteFork"):
			continue
		_forks.append({
			"fork_id": int(child.get_meta("fork_id")),
			"start_x": float(child.get_meta("start_x")),
			"split_x": float(child.get_meta("split_x")),
			"merge_x": float(child.get_meta("merge_x")),
			"end_x": float(child.get_meta("end_x")),
			"upper_max_y": float(child.get_meta("upper_max_y")),
			"lower_min_y": float(child.get_meta("lower_min_y")),
			"camera_margin": float(child.get_meta("camera_margin")),
			"target_camera_size": float(child.get_meta("target_camera_size")),
			"target_look_ahead": float(child.get_meta("target_look_ahead")),
		})
	_forks.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["start_x"] < b["start_x"])


func _fork_index_containing(world_x: float) -> int:
	for index in range(_forks.size()):
		var fork := _forks[index]
		if world_x >= float(fork["start_x"]) and world_x < float(fork["end_x"]):
			return index
	return -1


func _state_for_position(fork: Dictionary, world_x: float) -> String:
	if world_x < float(fork["split_x"]):
		return "APPROACH"
	if world_x < float(fork["merge_x"]):
		return "ACTIVE"
	return "EXIT"
