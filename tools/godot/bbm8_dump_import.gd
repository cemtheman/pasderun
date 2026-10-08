extends SceneTree

func _initialize() -> void:
	call_deferred("dump")

func dump() -> void:
	var scene = load("res://assets/characters/low_poly_girl/low_poly_girl .glb").instantiate()
	root.add_child(scene)
	var skeleton: Skeleton3D = scene.get_node("Rig/Skeleton3D")
	var rows: Array = []
	for i in skeleton.get_bone_count():
		var r := skeleton.get_bone_global_rest(i)
		rows.append({"name": String(skeleton.get_bone_name(i)), "parent": skeleton.get_bone_parent(i), "rest": encode(r)})
	var f := FileAccess.open("res://build/visual_validation/BBM-8/environment-probe/import_rest.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"bones": rows, "skeleton_transform": encode(skeleton.global_transform)}, "\t"))
	quit()

func encode(t: Transform3D) -> Array:
	return [[t.basis.x.x,t.basis.x.y,t.basis.x.z], [t.basis.y.x,t.basis.y.y,t.basis.y.z], [t.basis.z.x,t.basis.z.y,t.basis.z.z], [t.origin.x,t.origin.y,t.origin.z]]
