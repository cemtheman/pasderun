extends Node

const NORMAL_CAMERA_SIZE := 7.5
const NORMAL_LOOK_AHEAD := 1.75
const ENTRY_DURATION := 1.05
const EXIT_DURATION := 1.15

enum CameraState {
	NORMAL,
	APPROACHING_FORK,
	FORK_ACTIVE,
	LEAVING_FORK,
}

@export var camera_rig: Node3D
@export var camera: Camera3D
@export var target: Node3D
@export var course_root: Node3D

var _forks: Array[Dictionary] = []
var _next_fork_index := 0
var _active_index := -1
var _state := CameraState.NORMAL
var _frozen := false
var _transition_elapsed := 0.0
var _transition_duration := 0.0
var _start_size := NORMAL_CAMERA_SIZE
var _target_size := NORMAL_CAMERA_SIZE
var _start_look_ahead := NORMAL_LOOK_AHEAD
var _target_look_ahead := NORMAL_LOOK_AHEAD
var _start_rig_y := 0.0
var _target_rig_y := 0.0
var _normal_vertical_offset := 0.0


func _ready() -> void:
	process_priority = 20
	if camera_rig != null and target != null:
		_normal_vertical_offset = camera_rig.global_position.y - target.global_position.y
	_collect_fork_metadata()


func _process(delta: float) -> void:
	if _frozen or camera_rig == null or camera == null or target == null:
		return

	var world_x := target.global_position.x
	match _state:
		CameraState.NORMAL:
			if _next_fork_index < _forks.size() \
			and world_x >= float(_forks[_next_fork_index]["start_x"]):
				_begin_fork_entry(_next_fork_index)
		CameraState.APPROACHING_FORK:
			_apply_transition(delta)
			if _transition_elapsed >= _transition_duration:
				_state = CameraState.FORK_ACTIVE
				_apply_exact_targets()
		CameraState.FORK_ACTIVE:
			_apply_exact_targets()
			if world_x >= float(_forks[_active_index]["end_x"]):
				_begin_fork_exit()
		CameraState.LEAVING_FORK:
			_apply_transition(delta)
			if _transition_elapsed >= _transition_duration:
				_finish_fork_exit()


func set_frozen(value: bool) -> void:
	_frozen = value


func restore_normal_state() -> void:
	_active_index = -1
	_state = CameraState.NORMAL
	_transition_elapsed = 0.0
	_frozen = false
	_next_fork_index = _first_future_fork_index()
	if camera != null:
		camera.size = NORMAL_CAMERA_SIZE
	if camera_rig != null:
		camera_rig.set("look_ahead", NORMAL_LOOK_AHEAD)


func get_fork_state() -> String:
	match _state:
		CameraState.APPROACHING_FORK:
			return "APPROACH"
		CameraState.FORK_ACTIVE:
			return "ACTIVE"
		CameraState.LEAVING_FORK:
			return "EXIT"
	return "OUTSIDE"


func get_active_fork_id() -> int:
	if _active_index < 0:
		return 0
	return int(_forks[_active_index]["fork_id"])


func is_outside_fork() -> bool:
	return _state == CameraState.NORMAL


func _begin_fork_entry(index: int) -> void:
	_active_index = index
	_state = CameraState.APPROACHING_FORK
	var fork := _forks[index]
	var route_height := (
		float(fork["upper_max_y"])
		+ 2.0
		- float(fork["lower_min_y"])
	)
	var required_vertical_size := route_height + float(fork["camera_margin"]) * 2.0
	var route_center_y := (
		float(fork["lower_min_y"])
		+ float(fork["upper_max_y"])
		+ 2.0
	) * 0.5
	_capture_transition(
		maxf(float(fork["target_camera_size"]), required_vertical_size),
		float(fork["target_look_ahead"]),
		route_center_y - camera.position.y,
		ENTRY_DURATION
	)


func _begin_fork_exit() -> void:
	_state = CameraState.LEAVING_FORK
	_capture_transition(
		NORMAL_CAMERA_SIZE,
		NORMAL_LOOK_AHEAD,
		target.global_position.y + _normal_vertical_offset,
		EXIT_DURATION
	)


func _capture_transition(
	new_size: float,
	new_look_ahead: float,
	new_rig_y: float,
	duration: float
) -> void:
	_transition_elapsed = 0.0
	_transition_duration = duration
	_start_size = camera.size
	_target_size = new_size
	_start_look_ahead = float(camera_rig.get("look_ahead"))
	_target_look_ahead = new_look_ahead
	_start_rig_y = camera_rig.global_position.y
	_target_rig_y = new_rig_y


func _apply_transition(delta: float) -> void:
	_transition_elapsed = minf(_transition_elapsed + delta, _transition_duration)
	var linear_progress := _transition_elapsed / _transition_duration
	var eased_progress := _smoothstep(linear_progress)
	camera.size = lerpf(_start_size, _target_size, eased_progress)
	camera_rig.set(
		"look_ahead",
		lerpf(_start_look_ahead, _target_look_ahead, eased_progress)
	)
	camera_rig.global_position.y = lerpf(_start_rig_y, _target_rig_y, eased_progress)


func _apply_exact_targets() -> void:
	camera.size = _target_size
	camera_rig.set("look_ahead", _target_look_ahead)
	camera_rig.global_position.y = _target_rig_y


func _finish_fork_exit() -> void:
	camera.size = NORMAL_CAMERA_SIZE
	camera_rig.set("look_ahead", NORMAL_LOOK_AHEAD)
	_active_index = -1
	_next_fork_index += 1
	_state = CameraState.NORMAL
	_transition_elapsed = 0.0


func _smoothstep(value: float) -> float:
	var clamped := clampf(value, 0.0, 1.0)
	return clamped * clamped * (3.0 - 2.0 * clamped)


func _first_future_fork_index() -> int:
	if target == null:
		return 0
	for index in range(_forks.size()):
		if target.global_position.x < float(_forks[index]["start_x"]):
			return index
	return _forks.size()


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
			"end_x": float(child.get_meta("end_x")),
			"upper_max_y": float(child.get_meta("upper_max_y")),
			"lower_min_y": float(child.get_meta("lower_min_y")),
			"camera_margin": float(child.get_meta("camera_margin")),
			"target_camera_size": float(child.get_meta("target_camera_size")),
			"target_look_ahead": float(child.get_meta("target_look_ahead")),
		})
	_forks.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["start_x"] < b["start_x"])
