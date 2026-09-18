extends Node3D

## Presentation-only architectural skinning for music-derived route topologies.
## Collision bodies and geometry-plan coordinates remain authoritative.

@export_file("*.json") var geometry_plan_path: String = ""
@export var generated_level: Node3D
@export var safe_material: Material
@export var technical_material: Material
@export var crest_material: Material
@export var staircase_material: Material
@export var bridge_material: Material
@export var trim_material: Material

const SOAR := "SOAR"
const BRIDGE := "BRIDGE"
const CREST := "CREST"
const CRESCENDO_STAIRCASE := "CRESCENDO_STAIRCASE"

const FASCIA_HEIGHT := 0.12
const FASCIA_WIDTH_BLEED := 0.08
const FASCIA_TOP_INSET := 0.035

const CREST_SHELL_DEPTH := 0.36
const CREST_UNDERSIDE_SWELL := 0.10
const CREST_ARCH_SAMPLES := 18
const CREST_DEPTH_BLEED := 0.06
const CREST_NOSING_HEIGHT := 0.055

const STAIR_VISUAL_THICKNESS := 0.18
const STAIR_RISER_BOTTOM_INSET := 0.035
const STAIR_NOSING_HEIGHT := 0.045
const STAIR_NOSING_DEPTH_BLEED := 0.08
const STAIR_LOWER_BAND_HEIGHT := 0.022
const STAIR_LOWER_BAND_LENGTH_RATIO := 0.72

const SAFE_VISUAL_THICKNESS := 0.30
const SAFE_NOSING_HEIGHT := 0.045
const SAFE_DEPTH_BLEED := 0.06

const SOAR_VISUAL_EDGE_DEPTH := 0.28
const SOAR_ARCH_RISE := 0.04
const SOAR_ARCH_SAMPLES := 12
const SOAR_NOSING_HEIGHT := 0.05
const SOAR_DEPTH_BLEED := 0.06

const BRIDGE_VISUAL_EDGE_DEPTH := 0.26
const BRIDGE_ARCH_RISE := 0.04
const BRIDGE_ARCH_SAMPLES := 20
const BRIDGE_NOSING_HEIGHT := 0.045
const BRIDGE_DEPTH_BLEED := 0.08


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

	_skin_architectural_spans(plan)


func _skin_architectural_spans(plan: Dictionary) -> void:
	var overlays: Dictionary = plan.get("prototype_overlays", {})
	var spans_variant: Variant = overlays.get("architectural_spans_v1", [])
	if not spans_variant is Array:
		return
	var spans: Array = spans_variant
	for span_variant: Variant in spans:
		if not span_variant is Dictionary:
			continue
		var span: Dictionary = span_variant
		if String(span.get("topology", "")) != BRIDGE:
			continue
		_skin_bridge_span(plan, span)


func _skin_bridge_span(plan: Dictionary, span: Dictionary) -> void:
	var start_x := float(span["start_x"])
	var end_x := float(span["end_x"])
	var runways: Array = plan["surface_plan"]["runway_intervals"]
	var runway_index := -1
	for index in range(runways.size()):
		var runway: Dictionary = runways[index]
		if (
			abs(float(runway["start_x"]) - start_x) <= 0.001
			and abs(float(runway["end_x"]) - end_x) <= 0.001
		):
			runway_index = index
			break
	if runway_index < 0:
		push_error("PlatformSkinSystem BRIDGE runway was not found.")
		return

	var body := generated_level.get_node_or_null(
		"Level/Runway%02d" % (runway_index + 1)
	) as StaticBody3D
	if body == null:
		push_error("PlatformSkinSystem BRIDGE body was not found.")
		return

	var mesh_instance := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if mesh_instance == null or not mesh_instance.mesh is BoxMesh:
		return
	var base_box := mesh_instance.mesh as BoxMesh
	_set_collision_visual_hidden(body, true)

	var top_y := base_box.size.y * 0.5
	var bottom_edge_y := top_y - BRIDGE_VISUAL_EDGE_DEPTH
	var half_length := base_box.size.x * 0.5
	var profile := PackedVector2Array()
	profile.append(Vector2(-half_length, top_y))
	profile.append(Vector2(half_length, top_y))
	profile.append(Vector2(half_length, bottom_edge_y))
	for sample_index in range(BRIDGE_ARCH_SAMPLES, -1, -1):
		var t := float(sample_index) / float(BRIDGE_ARCH_SAMPLES)
		var x := lerpf(-half_length, half_length, t)
		var arch_y := bottom_edge_y + sin(PI * t) * BRIDGE_ARCH_RISE
		profile.append(Vector2(x, arch_y))

	var shell := MeshInstance3D.new()
	shell.name = "BridgeGalleryShell"
	shell.mesh = _build_extruded_profile(
		profile,
		base_box.size.z + BRIDGE_DEPTH_BLEED,
		bridge_material if bridge_material != null else technical_material
	)
	body.add_child(shell)

	_add_local_bridge_nosing(
		body,
		base_box.size.x,
		base_box.size.z + BRIDGE_DEPTH_BLEED + 0.04,
		top_y
	)


func _add_local_bridge_nosing(
	parent: Node3D,
	length: float,
	depth: float,
	top_y: float
) -> void:
	if trim_material == null:
		return
	var mesh := BoxMesh.new()
	mesh.size = Vector3(length, BRIDGE_NOSING_HEIGHT, depth)
	var nosing := MeshInstance3D.new()
	nosing.name = "BridgeGalleryNosing"
	nosing.mesh = mesh
	nosing.material_override = trim_material
	nosing.position = Vector3(
		0.0,
		top_y - BRIDGE_NOSING_HEIGHT * 0.5,
		0.0
	)
	parent.add_child(nosing)


func _skin_branch(event_number: int, branch: Dictionary) -> void:
	var routes: Dictionary = branch["routes"]
	var safe_body := generated_level.get_node_or_null(
		"Level/SafeLowerRoute%02d" % event_number
	) as StaticBody3D
	if safe_body != null:
		_apply_surface_material(safe_body, safe_material)
		_add_safe_architectural_deck(safe_body)

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

	if topology == SOAR:
		_add_soar_architectural_shell(event_number, collision_bodies)
		return

	for body in collision_bodies:
		_add_fascia(body, topology)


func _add_safe_architectural_deck(body: StaticBody3D) -> void:
	var base_mesh_instance := body.get_node_or_null("MeshInstance3D") as MeshInstance3D
	if base_mesh_instance == null or not base_mesh_instance.mesh is BoxMesh:
		return
	var base_box := base_mesh_instance.mesh as BoxMesh
	base_mesh_instance.visible = false

	var deck_mesh := BoxMesh.new()
	deck_mesh.size = Vector3(
		base_box.size.x,
		SAFE_VISUAL_THICKNESS,
		base_box.size.z
	)
	var deck := MeshInstance3D.new()
	deck.name = "SafeArchitecturalDeck"
	deck.mesh = deck_mesh
	deck.material_override = safe_material
	deck.position = Vector3(
		0.0,
		base_box.size.y * 0.5 - SAFE_VISUAL_THICKNESS * 0.5,
		0.0
	)
	body.add_child(deck)

	if trim_material == null:
		return
	var nosing_mesh := BoxMesh.new()
	nosing_mesh.size = Vector3(
		base_box.size.x,
		SAFE_NOSING_HEIGHT,
		base_box.size.z + SAFE_DEPTH_BLEED
	)
	var nosing := MeshInstance3D.new()
	nosing.name = "SafeGoldenNosing"
	nosing.mesh = nosing_mesh
	nosing.material_override = trim_material
	nosing.position = Vector3(
		0.0,
		base_box.size.y * 0.5 - SAFE_NOSING_HEIGHT * 0.5,
		0.0
	)
	body.add_child(nosing)


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
		var bottom_y := top_y - STAIR_VISUAL_THICKNESS
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
		_add_local_lower_band(
			body,
			base_box.size.x * STAIR_LOWER_BAND_LENGTH_RATIO,
			base_box.size.z + 0.02,
			bottom_y + STAIR_LOWER_BAND_HEIGHT * 0.5 + 0.018,
			"TheatricalRiserLowerBand%02d_%02d" % [event_number, body_index + 1]
		)


func _add_soar_architectural_shell(
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
		var bottom_edge_y := top_y - SOAR_VISUAL_EDGE_DEPTH
		var half_length := base_box.size.x * 0.5
		var profile := PackedVector2Array()
		profile.append(Vector2(-half_length, top_y))
		profile.append(Vector2(half_length, top_y))
		profile.append(Vector2(half_length, bottom_edge_y))
		for sample_index in range(SOAR_ARCH_SAMPLES, -1, -1):
			var t := float(sample_index) / float(SOAR_ARCH_SAMPLES)
			var x := lerpf(-half_length, half_length, t)
			var arch_y := bottom_edge_y + sin(PI * t) * SOAR_ARCH_RISE
			profile.append(Vector2(x, arch_y))

		var shell := MeshInstance3D.new()
		shell.name = "SoarGalleryShell%02d_%02d" % [event_number, body_index + 1]
		shell.mesh = _build_extruded_profile(
			profile,
			base_box.size.z + SOAR_DEPTH_BLEED,
			technical_material
		)
		body.add_child(shell)

		_add_local_soar_nosing(
			body,
			base_box.size.x,
			base_box.size.z + SOAR_DEPTH_BLEED + 0.04,
			top_y,
			"SoarGalleryNosing%02d_%02d" % [event_number, body_index + 1]
		)


func _add_local_soar_nosing(
	parent: Node3D,
	length: float,
	depth: float,
	top_y: float,
	node_name: String
) -> void:
	if trim_material == null:
		return
	var mesh := BoxMesh.new()
	mesh.size = Vector3(length, SOAR_NOSING_HEIGHT, depth)
	var nosing := MeshInstance3D.new()
	nosing.name = node_name
	nosing.mesh = mesh
	nosing.material_override = trim_material
	nosing.position = Vector3(
		0.0,
		top_y - SOAR_NOSING_HEIGHT * 0.5,
		0.0
	)
	parent.add_child(nosing)


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


func _add_local_lower_band(
	parent: Node3D,
	length: float,
	depth: float,
	center_y: float,
	node_name: String
) -> void:
	if trim_material == null:
		return
	var mesh := BoxMesh.new()
	mesh.size = Vector3(length, STAIR_LOWER_BAND_HEIGHT, depth)
	var band := MeshInstance3D.new()
	band.name = node_name
	band.mesh = mesh
	band.material_override = trim_material
	band.position = Vector3(0.0, center_y, 0.0)
	parent.add_child(band)


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
