extends Node3D

## Collision-aware smoothing and architectural treatment for the shared mainline.
## Existing generated runway bodies remain authoritative unless a small passive
## height transition is replaced one-for-one by a shallow ramp collision.

@export_file("*.json") var geometry_plan_path: String = ""
@export var generated_level: Node3D
@export var mainline_material: Material
@export var trim_material: Material

const GROUND_HEIGHT := 0.5
const GROUND_WIDTH := 4.0
const MAX_SMOOTH_DELTA := 0.20
const CONTIGUITY_EPSILON := 0.002
const FLAT_EPSILON := 0.0005
const TRIM_HEIGHT := 0.045
const TRIM_DEPTH_BLEED := 0.08
const BRIDGE := "BRIDGE"


func _ready() -> void:
	if generated_level == null:
		push_error("MainlineContinuitySystem requires generated_level.")
		return
	if geometry_plan_path.is_empty():
		push_error("MainlineContinuitySystem requires geometry_plan_path.")
		return

	var file := FileAccess.open(geometry_plan_path, FileAccess.READ)
	if file == null:
		push_error("MainlineContinuitySystem could not open geometry plan: %s" % geometry_plan_path)
		return

	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		push_error("MainlineContinuitySystem geometry plan is invalid.")
		return

	_apply_mainline_continuity(parsed)


func _apply_mainline_continuity(plan: Dictionary) -> void:
	var surface_plan_variant: Variant = plan.get("surface_plan", {})
	if not surface_plan_variant is Dictionary:
		return
	var surface_plan: Dictionary = surface_plan_variant
	var runways_variant: Variant = surface_plan.get("runway_intervals", [])
	if not runways_variant is Array:
		return
	var runways: Array = runways_variant
	var excluded_spans := _excluded_architectural_spans(plan)

	var group: Array = []
	for runway_index in range(runways.size()):
		var runway_variant: Variant = runways[runway_index]
		if not runway_variant is Dictionary:
			continue
		var runway: Dictionary = runway_variant
		var item := {
			"runway_index": runway_index,
			"start_x": float(runway["start_x"]),
			"end_x": float(runway["end_x"]),
			"surface_y": float(runway["surface_y"]),
		}

		if _overlaps_any_span(
			float(item["start_x"]),
			float(item["end_x"]),
			excluded_spans
		):
			_flush_group(group)
			group = []
			continue

		if group.is_empty():
			group.append(item)
			continue

		var previous: Dictionary = group[-1]
		var contiguous: bool = (
			abs(float(previous["end_x"]) - float(item["start_x"]))
			<= CONTIGUITY_EPSILON
		)
		var smooth_delta: bool = (
			abs(float(previous["surface_y"]) - float(item["surface_y"]))
			<= MAX_SMOOTH_DELTA
		)
		if contiguous and smooth_delta:
			group.append(item)
		else:
			_flush_group(group)
			group = [item]

	_flush_group(group)

	# Runways that were excluded from smoothing still need the architectural
	# family treatment unless a topology-specific skin owns them.
	for runway_index in range(runways.size()):
		var runway: Dictionary = runways[runway_index]
		var start_x := float(runway["start_x"])
		var end_x := float(runway["end_x"])
		if _overlaps_any_span(start_x, end_x, excluded_spans):
			continue
		var body := _runway_body(runway_index)
		if body == null:
			continue
		var collision := body.get_node_or_null("CollisionShape3D") as CollisionShape3D
		if collision != null and collision.disabled:
			continue
		_style_existing_runway(body)


func _flush_group(group: Array) -> void:
	if group.is_empty():
		return

	var has_height_change := false
	for index in range(1, group.size()):
		var previous: Dictionary = group[index - 1]
		var current: Dictionary = group[index]
		if abs(
			float(previous["surface_y"]) - float(current["surface_y"])
		) > FLAT_EPSILON:
			has_height_change = true
			break

	if group.size() < 2 or not has_height_change:
		for item_variant: Variant in group:
			var item: Dictionary = item_variant
			var body := _runway_body(int(item["runway_index"]))
			if body != null:
				_style_existing_runway(body)
		return

	var boundary_y: Array[float] = []
	var first: Dictionary = group[0]
	boundary_y.append(float(first["surface_y"]))
	for index in range(1, group.size()):
		var left: Dictionary = group[index - 1]
		var right: Dictionary = group[index]
		boundary_y.append(
			(float(left["surface_y"]) + float(right["surface_y"])) * 0.5
		)
	var last: Dictionary = group[-1]
	boundary_y.append(float(last["surface_y"]))

	for index in range(group.size()):
		var item: Dictionary = group[index]
		var body := _runway_body(int(item["runway_index"]))
		if body == null:
			continue
		_disable_generated_runway(body)
		_add_shallow_ramp(
			int(item["runway_index"]),
			float(item["start_x"]),
			float(item["end_x"]),
			boundary_y[index],
			boundary_y[index + 1]
		)


func _runway_body(runway_index: int) -> StaticBody3D:
	return generated_level.get_node_or_null(
		"Level/Runway%02d" % (runway_index + 1)
	) as StaticBody3D


func _disable_generated_runway(body: StaticBody3D) -> void:
	var mesh := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if mesh != null:
		mesh.visible = false
	var collision := body.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if collision != null:
		collision.set_deferred("disabled", true)


func _style_existing_runway(body: StaticBody3D) -> void:
	var mesh := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if mesh == null or not mesh.mesh is BoxMesh:
		return
	if mainline_material != null:
		mesh.material_override = mainline_material
	if trim_material == null or body.has_node("MainlineGoldenNosing"):
		return
	var base_box := mesh.mesh as BoxMesh
	var trim_mesh := BoxMesh.new()
	trim_mesh.size = Vector3(
		base_box.size.x,
		TRIM_HEIGHT,
		base_box.size.z + TRIM_DEPTH_BLEED
	)
	var trim := MeshInstance3D.new()
	trim.name = "MainlineGoldenNosing"
	trim.mesh = trim_mesh
	trim.material_override = trim_material
	trim.position = Vector3(
		0.0,
		base_box.size.y * 0.5 - TRIM_HEIGHT * 0.5,
		0.0
	)
	body.add_child(trim)


func _add_shallow_ramp(
	runway_index: int,
	start_x: float,
	end_x: float,
	start_surface_y: float,
	end_surface_y: float
) -> void:
	var dx := end_x - start_x
	if dx <= 0.0:
		return
	var dy := end_surface_y - start_surface_y
	var length: float = sqrt(dx * dx + dy * dy)
	var angle := atan2(dy, dx)
	var normal_x := -sin(angle)
	var normal_y := cos(angle)
	var midpoint_x := (start_x + end_x) * 0.5
	var midpoint_y := (start_surface_y + end_surface_y) * 0.5
	var center_x := midpoint_x - normal_x * GROUND_HEIGHT * 0.5
	var center_y := midpoint_y - normal_y * GROUND_HEIGHT * 0.5

	var body := StaticBody3D.new()
	body.name = "MainlineShallowRamp%02d" % (runway_index + 1)
	body.position = Vector3(center_x, center_y, 0.0)
	body.rotation = Vector3(0.0, 0.0, angle)

	var mesh_resource := BoxMesh.new()
	mesh_resource.size = Vector3(length, GROUND_HEIGHT, GROUND_WIDTH)
	var mesh := MeshInstance3D.new()
	mesh.name = "MeshInstance3D"
	mesh.mesh = mesh_resource
	if mainline_material != null:
		mesh.material_override = mainline_material
	body.add_child(mesh)

	var shape_resource := BoxShape3D.new()
	shape_resource.size = Vector3(length, GROUND_HEIGHT, GROUND_WIDTH)
	var collision := CollisionShape3D.new()
	collision.name = "CollisionShape3D"
	collision.shape = shape_resource
	body.add_child(collision)

	if trim_material != null:
		var trim_resource := BoxMesh.new()
		trim_resource.size = Vector3(
			length,
			TRIM_HEIGHT,
			GROUND_WIDTH + TRIM_DEPTH_BLEED
		)
		var trim := MeshInstance3D.new()
		trim.name = "MainlineGoldenNosing"
		trim.mesh = trim_resource
		trim.material_override = trim_material
		trim.position = Vector3(
			0.0,
			GROUND_HEIGHT * 0.5 - TRIM_HEIGHT * 0.5,
			0.0
		)
		body.add_child(trim)

	var level := generated_level.get_node_or_null("Level")
	if level != null:
		level.add_child(body)


func _excluded_architectural_spans(plan: Dictionary) -> Array[Vector2]:
	var result: Array[Vector2] = []
	var overlays_variant: Variant = plan.get("prototype_overlays", {})
	if not overlays_variant is Dictionary:
		return result
	var overlays: Dictionary = overlays_variant
	var spans_variant: Variant = overlays.get("architectural_spans_v1", [])
	if not spans_variant is Array:
		return result
	for span_variant: Variant in spans_variant:
		if not span_variant is Dictionary:
			continue
		var span: Dictionary = span_variant
		if String(span.get("topology", "")) != BRIDGE:
			continue
		result.append(Vector2(
			float(span["start_x"]),
			float(span["end_x"])
		))
	return result


func _overlaps_any_span(
	start_x: float,
	end_x: float,
	spans: Array[Vector2]
) -> bool:
	for span in spans:
		if (
			end_x > span.x + CONTIGUITY_EPSILON
			and start_x < span.y - CONTIGUITY_EPSILON
		):
			return true
	return false
