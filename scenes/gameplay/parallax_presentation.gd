extends Node3D

@export var progress_source: Node3D
@export var far_layer: MeshInstance3D
@export var mid_layer: MeshInstance3D
@export var foreground_layer: MeshInstance3D
@export var far_factor: float = 0.005
@export var mid_factor: float = 0.010
@export var foreground_factor: float = 0.018
@export var pace_multiplier: float = 1.75

var _initial_world_x: float
var _far_initial_x: float
var _mid_initial_x: float
var _foreground_initial_x: float


func _ready() -> void:
	if (
		progress_source == null
		or far_layer == null
		or mid_layer == null
		or foreground_layer == null
	):
		push_error("ParallaxPresentation requires progress source and three layers.")
		set_process(false)
		return

	_initial_world_x = progress_source.global_position.x
	_far_initial_x = far_layer.position.x
	_mid_initial_x = mid_layer.position.x
	_foreground_initial_x = foreground_layer.position.x


func _process(_delta: float) -> void:
	var progress_x := progress_source.global_position.x - _initial_world_x
	var paced_progress_x := progress_x * pace_multiplier
	far_layer.position.x = _far_initial_x - paced_progress_x * far_factor
	mid_layer.position.x = _mid_initial_x - paced_progress_x * mid_factor
	foreground_layer.position.x = (
		_foreground_initial_x - paced_progress_x * foreground_factor
	)
