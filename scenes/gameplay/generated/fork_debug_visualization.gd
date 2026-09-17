extends Node3D

enum DiagnosticMode {
	OFF,
	ROUTES,
	MARKERS,
	LABELS,
	ALL,
}

const MODE_NAMES := ["OFF", "ROUTES", "MARKERS", "LABELS", "ALL"]

@export var generated_level: Node3D
@export var safe_color: Color = Color(0.10, 0.75, 1.0, 1.0)
@export var technical_color: Color = Color(1.0, 0.35, 0.08, 1.0)
@export var split_color: Color = Color(0.25, 1.0, 0.35, 1.0)
@export var merge_color: Color = Color(1.0, 0.20, 0.75, 1.0)

var _diagnostic_mode := DiagnosticMode.ALL
var _route_meshes: Array = []
var _route_original_materials: Array = []
var _route_debug_materials: Array = []
var _marker_meshes: Array[MeshInstance3D] = []
var _marker_labels: Array[Label3D] = []


func _ready() -> void:
	if generated_level == null:
		return

	var level := generated_level.get_node_or_null("Level")
	if level == null:
		return

	var safe_material := _debug_material(safe_color)
	var technical_material := _debug_material(technical_color)
	var split_material := _debug_material(split_color)
	var merge_material := _debug_material(merge_color)

	for child in level.get_children():
		var node_name := String(child.name)
		if node_name.begins_with("SafeLowerRoute"):
			_register_route(child, safe_material)
		elif node_name.begins_with("TechnicalRoute"):
			_register_route(child, technical_material)
		elif node_name.begins_with("ForkStart") and child is Marker3D:
			_add_marker(child as Marker3D, "FORK START", split_color, split_material)
		elif node_name.begins_with("ForkMerge") and child is Marker3D:
			_add_marker(child as Marker3D, "FORK MERGE", merge_color, merge_material)

	set_diagnostic_mode(DiagnosticMode.ALL)


func _debug_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return material


func _register_route(body: Node, material: StandardMaterial3D) -> void:
	var mesh := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if mesh != null:
		_route_meshes.append(mesh)
		_route_original_materials.append(mesh.material_override)
		_route_debug_materials.append(material)


func _add_marker(
	source: Marker3D,
	marker_text: String,
	color: Color,
	material: StandardMaterial3D
) -> void:
	var marker_root := Node3D.new()
	marker_root.name = marker_text.replace(" ", "")
	add_child(marker_root)
	marker_root.global_position = source.global_position

	var marker_mesh := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.22
	sphere.height = 0.44
	marker_mesh.mesh = sphere
	marker_mesh.material_override = material
	marker_root.add_child(marker_mesh)
	_marker_meshes.append(marker_mesh)

	var label := Label3D.new()
	label.text = marker_text
	label.position = Vector3(0, 0.55, 0)
	label.font_size = 48
	label.outline_size = 8
	label.modulate = color
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	marker_root.add_child(label)
	_marker_labels.append(label)


func set_diagnostic_mode(mode: int) -> void:
	_diagnostic_mode = clampi(mode, DiagnosticMode.OFF, DiagnosticMode.ALL)
	var show_routes := (
		_diagnostic_mode == DiagnosticMode.ROUTES
		or _diagnostic_mode == DiagnosticMode.ALL
	)
	var show_markers := (
		_diagnostic_mode == DiagnosticMode.MARKERS
		or _diagnostic_mode == DiagnosticMode.ALL
	)
	var show_labels := (
		_diagnostic_mode == DiagnosticMode.LABELS
		or _diagnostic_mode == DiagnosticMode.ALL
	)

	for index in _route_meshes.size():
		_route_meshes[index].material_override = (
			_route_debug_materials[index]
			if show_routes
			else _route_original_materials[index]
		)
	for marker_mesh in _marker_meshes:
		marker_mesh.visible = show_markers
	for marker_label in _marker_labels:
		marker_label.visible = show_labels


func get_diagnostic_mode_name() -> String:
	return MODE_NAMES[_diagnostic_mode]
