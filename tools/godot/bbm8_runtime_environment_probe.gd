extends SceneTree

var runtime: Node
var frames := 0
var trace: Array = []

func _initialize() -> void:
	call_deferred("begin")

func begin() -> void:
	runtime = load("res://scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn").instantiate()
	root.add_child(runtime)

func _process(_delta: float) -> bool:
	if runtime == null:
		return false
	frames += 1
	var dancer: CharacterBody3D = runtime.get_node("Dancer")
	var gate: Node = runtime.get_node("RuntimeStartGate")
	var visual: Node = dancer.get_node("BallerinaVisualV1")
	if frames % 30 == 0:
		trace.append({"frame": frames, "prelude": gate.get("_prelude_state"), "visual": String(visual.call("get_visual_state")), "grounded": dancer.is_on_floor(), "position": [dancer.position.x,dancer.position.y,dancer.position.z]})
	if frames >= 360:
		var skeleton: Skeleton3D = visual.get_node("low_poly_girl/Rig/Skeleton3D")
		var poses: Array = []
		for i in skeleton.get_bone_count():
			poses.append({"name": String(skeleton.get_bone_name(i)), "pose": encode(skeleton.get_bone_global_pose(i))})
		var output := {"status": "DIAGNOSTIC_ONLY", "bbm8_integration": "NOT_IMPLEMENTED", "engine": Engine.get_version_info(), "display_driver": DisplayServer.get_name(), "rendering_method": RenderingServer.get_current_rendering_method(), "trace": trace, "ready_global_poses": poses, "scope": "actual main gameplay scene environment probe; no BBM lifecycle or visual PASS"}
		var file := FileAccess.open("res://build/visual_validation/BBM-8/environment-probe/runtime.json", FileAccess.WRITE)
		file.store_string(JSON.stringify(output,"\t"))
		quit()
	return false

func encode(t: Transform3D) -> Array:
	return [[t.basis.x.x,t.basis.x.y,t.basis.x.z], [t.basis.y.x,t.basis.y.y,t.basis.y.z], [t.basis.z.x,t.basis.z.y,t.basis.z.z], [t.origin.x,t.origin.y,t.origin.z]]
