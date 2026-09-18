extends Node3D

@export var recovery_manager: Node

var _markers: Dictionary = {}
var _active_index := -1


func _ready() -> void:
	if recovery_manager == null or not recovery_manager.has_signal("checkpoint_changed"):
		push_error("CheckpointVisualization requires RunRecoveryManager checkpoint_changed.")
		return
	recovery_manager.connect(
		"checkpoint_changed",
		Callable(self, "_on_checkpoint_changed")
	)


func _on_checkpoint_changed(
	_checkpoint_id: String,
	checkpoint_index: int,
	checkpoint_position: Vector3
) -> void:
	if _active_index >= 0 and _markers.has(_active_index):
		var previous := _markers[_active_index] as Node3D
		if is_instance_valid(previous):
			previous.scale = Vector3.ONE * 0.78

	var marker: Node3D
	if _markers.has(checkpoint_index):
		marker = _markers[checkpoint_index] as Node3D
	else:
		marker = _build_marker(checkpoint_index)
		_markers[checkpoint_index] = marker
		add_child(marker)

	marker.position = Vector3(
		checkpoint_position.x,
		checkpoint_position.y - 1.12,
		-0.42
	)
	marker.scale = Vector3.ONE * 1.08
	_active_index = checkpoint_index


func _build_marker(checkpoint_index: int) -> Node3D:
	var root := Node3D.new()
	root.name = "CheckpointMarker%02d" % checkpoint_index

	var gold := StandardMaterial3D.new()
	gold.albedo_color = Color(0.78, 0.56, 0.23, 1.0)
	gold.roughness = 0.32
	gold.emission_enabled = true
	gold.emission = Color(0.40, 0.20, 0.055, 1.0)

	var stem_mesh := BoxMesh.new()
	stem_mesh.size = Vector3(0.035, 0.48, 0.08)
	var stem := MeshInstance3D.new()
	stem.name = "Stem"
	stem.mesh = stem_mesh
	stem.material_override = gold
	stem.position = Vector3(0.0, 0.24, 0.0)
	root.add_child(stem)

	var diamond_mesh := BoxMesh.new()
	diamond_mesh.size = Vector3(0.20, 0.20, 0.10)
	var diamond := MeshInstance3D.new()
	diamond.name = "Diamond"
	diamond.mesh = diamond_mesh
	diamond.material_override = gold
	diamond.position = Vector3(0.0, 0.55, 0.0)
	diamond.rotation.z = PI * 0.25
	root.add_child(diamond)

	return root
