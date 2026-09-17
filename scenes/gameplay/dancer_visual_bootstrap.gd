extends Node

const DANCER_VISUAL_SCRIPT := preload("res://scenes/gameplay/dancer_visual_motion_v5.gd")
const DANCER_TAP_FEEDBACK_SCRIPT := preload("res://scenes/gameplay/dancer_tap_feedback.gd")


func _ready() -> void:
	get_tree().node_added.connect(_on_node_added)
	call_deferred("_attach_existing_dancer")


func _on_node_added(node: Node) -> void:
	if node is CharacterBody3D and node.name == &"Dancer":
		call_deferred("_attach_visual", node)


func _attach_existing_dancer() -> void:
	var scene := get_tree().current_scene
	if scene == null:
		return
	var dancer := scene.get_node_or_null("Dancer")
	if dancer is CharacterBody3D:
		_attach_visual(dancer)


func _attach_visual(dancer: CharacterBody3D) -> void:
	if not is_instance_valid(dancer):
		return

	var visual := dancer.get_node_or_null("DancerVisual")
	if visual == null:
		visual = DANCER_VISUAL_SCRIPT.new()
		visual.name = "DancerVisual"
		dancer.add_child(visual)

	# Keep the accepted capsule visible unless the replacement visual actually
	# initialized its rig. A Phase 7 presentation failure must not make the
	# gameplay body disappear during development/runtime QA.
	if visual.get_node_or_null("Rig") == null:
		push_error("DancerVisual failed to initialize; keeping capsule fallback visible.")
		return

	var capsule_visual := dancer.get_node_or_null("MeshInstance3D")
	if capsule_visual is GeometryInstance3D:
		capsule_visual.visible = false

	if dancer.get_node_or_null("TapVisualFeedback") == null:
		var tap_feedback := DANCER_TAP_FEEDBACK_SCRIPT.new()
		tap_feedback.name = "TapVisualFeedback"
		dancer.add_child(tap_feedback)
