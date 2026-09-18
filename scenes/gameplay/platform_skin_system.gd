extends Node3D

## Presentation-only architectural skinning for music-derived route topologies.
## Collision bodies and geometry-plan coordinates remain authoritative.

@export_file("*.json") var geometry_plan_path: String = ""
@export var generated_level: Node3D
@export var safe_material: Material
@export var technical_material: Material
@export var crest_material: Material
@export var staircase_material: Material
@export var trim_material: Material

const CREST := "CREST"
const CRESCENDO_STAIRCASE := "CRESCENDO_STAIRCASE"

const FASCIA_HEIGHT := 0.12
const FASCIA_WIDTH_BLEED := 0.08
const FASCIA_TOP_INSET := 0.035

const CREST_SHELL_DEPTH := 0.52
const CREST_UNDERSIDE_SWELL := 0.20
const CREST_ARCH_SAMPLES := 18
const CREST_DEPTH_BLEED := 0.06
const CREST_NOSING_HEIGHT := 0.055

const STAIR_RISER_EXTRA_DEPTH := 0.12
const STAIR_RISER_BOTTOM_INSET := 0.14
const STAIR_NOSING_HEIGHT := 0.065
const STAIR_NOSING_DEPTH_BLEED := 0.10


func _ready() -> void:
	if generated_level == null:
		push_error("PlatformSkinSystem requires generated_level.")
		return
	if geometry_plan_path.is_empty():
		push_error("PlatformSkinSystem requires geometry_plan_path.")
		return

	var file := FileAccess.open(geometry_plan_path, FileAccess.READ)
	if file == null:
		push_error("PlatformSkinSystem could not open geometry plan: %s" % geometry_plan_path)
		return

	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		push_error("PlatformSkinSystem geometry plan is invalid.")
		return

	var plan: Dictionary = parsed
	var events: Array = plan.get("events", [])
	for event_index in range(events.size()):
		var event: Dictionary = events[event_index]
		var branch_variant: Variant = event.get("branch")
		if branch_variant == null or not branch_variant is Dictionary:
			continue
		_skin_branch(event_index + 1, branch_variant)


func _skin_branch(event_number: int, branch: Dictionary) -> void:
	var routes: Dictionary = branch["routes"]
	var safe_body := generated_level.get_node_or_null(
		"Level/SafeLowerRoute%02d" % event_number
	) as StaticBody3D
	if safe_body != null:
		_apply_surface_material(safe_body, safe_material)

	var topology := String(branch.get("topology", "SOAR"))
	var technical: Dictionary = routes["technical"]
	var technical_skin := _material_for_topology(topology)
	var collision_index := 0
	var collision_bodies: Array[StaticBody3D] = []

	for segment_variant: Variant in technical["segments"]:
		var segment: Dictionary = segment_variant
		if not bool(segment.get("collision", false)):
			continue
		collision_index += 1
		var technical_body := generated_level.get_node_or_null(
			"Level/TechnicalRoute%02d_%02d" % [event_number, collision_index]
		) as StaticBody3D
		if technical_body == null:
			continue
		collision_bodies.append(technical_body)
		_apply_surface_material(technical_body, technical_skin)

	if topology == CREST:
		_add_crest_architectural_shell(event_number, technical, collision_bodies)
		return

	if topology == CRESCENDO_STAIRCASE:
		_add_staircase_architectural_shell(event_number, collision_bodies)
		return

	for body in collision_bodies:
		_add_fascia(body, topology)


func _material_for_topology(topology: String) -> Material:
	if topology == CREST and crest_material != null:
		return crest_material
	if topology == CRESCENDO_STAIRCASE and staircase_material != null:
		return staircase_material
	return technical_material


func _apply_surface_material(body: StaticBody3D, material: Material) -> void:
	if material == null:
		return
	var mesh_instance := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if mesh_instance == null:
		return
	mesh_instance.material_override = material


func _add_fascia(body: StaticBody3D, topology: String) -> void:
	if trim_material == null or body.has_node("PlatformSkinFascia"):
		return
	var base_mesh_instance := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if base_mesh_instance == null:
		return
	var base_box := base_mesh_instance.mesh as BoxMesh
	if base_box == null:
		return

	var fascia_mesh := BoxMesh.new()
	var fascia_height := FASCIA_HEIGHT
	fascia_mesh.size = Vector3(
		base_box.size.x,
		fascia_height,
		base_box.size.z + FASCIA_WIDTH_BLEED
	)

	var fascia := MeshInstance3D.new()
	fascia.name = "PlatformSkinFascia"
	fascia.mesh = fascia_mesh
	fascia.material_override = trim_material
	fascia.position = Vector3(
		0.0,
		base_box.size.y * 0.5 - fascia_height * 0.5 - FASCIA_TOP_INSET,
		0.0
	)
	body.add_child(fascia)


func _add_crest_architectural_shell(
	event_number: int,
	technical: Dictionary,
	collision_bodies: Array[StaticBody3D]
) -> void:
	if collision_bodies.is_empty():
		return

	var crest_segments: Array[Dictionary] = []
	for segment_variant: Variant in technical["segments"]:
		var segment: Dictionary = segment_variant
		if bool(segment.get("collision", false)) and String(segment["type"]).begins_with("CREST_TERRACE_"):
			crest_segments.append(segment)
	if crest_segments.is_empty():
		return

	for body in collision_bodies:
		_set_collision_visual_hidden(body, true)

	var first_mesh := collision_bodies[0].get_node_or_null("MeshInstance3D") as MeshInstance3D
	if first_mesh == null or not first_mesh.mesh is BoxMesh:
		return
	var base_box := first_mesh.mesh as BoxMesh
	var shell_width := base_box.size.z + CREST_DEPTH_BLEED

	var profile := PackedVector2Array()
	for segment_index in range(crest_segments.size()):
		var segment: Dictionary = crest_segments[segment_index]
		var start_x := float(segment["start_x"])
		var end_x := float(segment["end_x"])
		var surface_y := float(segment["surface_y"])
		if segment_index == 0:
			profile.append(Vector2(start_x, surface_y))
		profile.append(Vector2(end_x, surface_y))
		if segment_index + 1 < crest_segments.size():
			var next_y := float(crest_segments[segment_index + 1]["surface_y"])
			profile.append(Vector2(end_x, next_y))

	var profile_start_x := float(crest_segments[0]["start_x"])
	var profile_end_x := float(crest_segments[-1]["end_x"])
	var base_y := float(technical["elevation"])
	for sample_index in range(CREST_ARCH_SAMPLES, -1, -1):
		var t := float(sample_index) / float(CREST_ARCH_SAMPLES)
		var x := lerpf(profile_start_x, profile_end_x, t)
		var underside := (
			base_y
			- CREST_SHELL_DEPTH
			- sin(PI * t) * CREST_UNDERSIDE_SWELL
		)
		profile.append(Vector2(x, underside))

	var level := generated_level.get_node_or_null("Level")
	if level == null:
		return
	var shell := MeshInstance3D.new()
	shell.name = "CrestArchitecturalShell%02d" % event_number
	shell.mesh = _build_extruded_profile(profile, shell_width, crest_material)
	level.add_child(shell)

	for segment_index in range(crest_segments.size()):
		var segment: Dictionary = crest_segments[segment_index]
		_add_absolute_nosing(
			level,
			"CrestNosing%02d_%02d" % [event_number, segment_index + 1],
			float(segment["start_x"]),
			float(segment["end_x"]),
			float(segment["surface_y"]),
			shell_width,
			CREST_NOSING_HEIGHT
		)


func _add_staircase_architectural_shell(
	event_number: int,
	collision_bodies: Array[StaticBody3D]
) -> void:
	for body_index in range(collision_bodies.size()):
		var body := collision_bodies[body_index]
		var mesh_instance := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
		if mesh_instance == null or not mesh_instance.mesh is BoxMesh:
			continue
		var base_box := mesh_instance.mesh as BoxMesh
		_set_collision_visual_hidden(body, true)

		var top_y := base_box.size.y * 0.5
		var bottom_y := -base_box.size.y * 0.5 - STAIR_RISER_EXTRA_DEPTH
		var half_top := base_box.size.x * 0.5
		var half_bottom := maxf(
			0.12,
			half_top - STAIR_RISER_BOTTOM_INSET
		)
		var profile := PackedVector2Array([
			Vector2(-half_top, top_y),
			Vector2(half_top, top_y),
			Vector2(half_bottom, bottom_y),
			Vector2(-half_bottom, bottom_y),
		])

		var shell := MeshInstance3D.new()
		shell.name = "TheatricalRiserShell%02d_%02d" % [event_number, body_index + 1]
		shell.mesh = _build_extruded_profile(
			profile,
			base_box.size.z,
			staircase_material
		)
		body.add_child(shell)
		_add_local_nosing(
			body,
			base_box.size.x,
			base_box.size.z + STAIR_NOSING_DEPTH_BLEED,
			top_y,
			"TheatricalRiserNosing%02d_%02d" % [event_number, body_index + 1]
		)


func _set_collision_visual_hidden(body: StaticBody3D, hidden: bool) -> void:
	var mesh_instance := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if mesh_instance != null:
		mesh_instance.visible = not hidden


func _add_absolute_nosing(
	parent: Node,
	node_name: String,
	start_x: float,
	end_x: float,
	surface_y: float,
	depth: float,
	height: float
) -> void:
	if trim_material == null:
		return
	var mesh := BoxMesh.new()
	mesh.size = Vector3(end_x - start_x, height, depth)
	var nosing := MeshInstance3D.new()
	nosing.name = node_name
	nosing.mesh = mesh
	nosing.material_override = trim_material
	nosing.position = Vector3(
		(start_x + end_x) * 0.5,
		surface_y - height * 0.5,
		0.0
	)
	parent.add_child(nosing)


func _add_local_nosing(
	parent: Node3D,
	length: float,
	depth: float,
	top_y: float,
	node_name: String
) -> void:
	if trim_material == null:
		return
	var mesh := BoxMesh.new()
	mesh.size = Vector3(length, STAIR_NOSING_HEIGHT, depth)
	var nosing := MeshInstance3D.new()
	nosing.name = node_name
	nosing.mesh = mesh
	nosing.material_override = trim_material
	nosing.position = Vector3(
		0.0,
		top_y - STAIR_NOSING_HEIGHT * 0.5,
		0.0
	)
	parent.add_child(nosing)


func _build_extruded_profile(
	profile: PackedVector2Array,
	depth: float,
	material: Material
) -> ArrayMesh:
	var triangulated := Geometry2D.triangulate_polygon(profile)
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	if material != null:
		surface.set_material(material)

	var front_z := depth * 0.5
	var back_z := -depth * 0.5

	for triangle_index in range(0, triangulated.size(), 3):
		var a := profile[triangulated[triangle_index]]
		var b := profile[triangulated[triangle_index + 1]]
		var c := profile[triangulated[triangle_index + 2]]
		_add_triangle(
			surface,
			Vector3(a.x, a.y, front_z),
			Vector3(b.x, b.y, front_z),
			Vector3(c.x, c.y, front_z)
		)
		_add_triangle(
			surface,
			Vector3(c.x, c.y, back_z),
			Vector3(b.x, b.y, back_z),
			Vector3(a.x, a.y, back_z)
		)

	for edge_index in range(profile.size()):
		var next_index := (edge_index + 1) % profile.size()
		var a := profile[edge_index]
		var b := profile[next_index]
		_add_quad(
			surface,
			Vector3(a.x, a.y, front_z),
			Vector3(b.x, b.y, front_z),
			Vector3(b.x, b.y, back_z),
			Vector3(a.x, a.y, back_z)
		)

	surface.generate_normals()
	return surface.commit()


func _add_triangle(
	surface: SurfaceTool,
	a: Vector3,
	b: Vector3,
	c: Vector3
) -> void:
	surface.add_vertex(a)
	surface.add_vertex(b)
	surface.add_vertex(c)


func _add_quad(
	surface: SurfaceTool,
	a: Vector3,
	b: Vector3,
	c: Vector3,
	d: Vector3
) -> void:
	_add_triangle(surface, a, b, c)
	_add_triangle(surface, a, c, d)
