extends Node3D

## Presentation-only platform skinning for music-derived route topologies.
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
		_apply_surface_material(technical_body, technical_skin)
		_add_fascia(technical_body, topology)


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
	if topology == CRESCENDO_STAIRCASE:
		fascia_height = 0.15
	elif topology == CREST:
		fascia_height = 0.10

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
