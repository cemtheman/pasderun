extends Node3D

const PULSE_DURATION := 0.18
const PULSE_START_SCALE := 0.72
const PULSE_END_SCALE := 1.42

var dancer: CharacterBody3D
var _ring: MeshInstance3D
var _remaining := 0.0


func _ready() -> void:
	dancer = get_parent() as CharacterBody3D
	if dancer == null or not dancer.has_signal(&"tap_detected"):
		push_error("DancerTapFeedback requires Dancer.tap_detected.")
		queue_free()
		return

	_build_ring()
	dancer.connect(&"tap_detected", Callable(self, "_on_tap_detected"))
	set_process(false)


func _process(delta: float) -> void:
	_remaining = maxf(_remaining - delta, 0.0)
	var progress := 1.0 - (_remaining / PULSE_DURATION)
	var scale_value := lerpf(PULSE_START_SCALE, PULSE_END_SCALE, progress)
	_ring.scale = Vector3.ONE * scale_value
	_ring.transparency = lerpf(0.08, 1.0, progress)
	if _remaining <= 0.0:
		_ring.visible = false
		set_process(false)


func _on_tap_detected() -> void:
	_remaining = PULSE_DURATION
	_ring.visible = true
	_ring.scale = Vector3.ONE * PULSE_START_SCALE
	_ring.transparency = 0.08
	set_process(true)


func _build_ring() -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.94, 0.80, 0.48, 1.0)
	material.emission_enabled = true
	material.emission = Color(0.94, 0.72, 0.34, 1.0)
	material.emission_energy_multiplier = 1.35
	material.roughness = 0.45

	var mesh := TorusMesh.new()
	mesh.inner_radius = 0.31
	mesh.outer_radius = 0.36

	_ring = MeshInstance3D.new()
	_ring.name = "TapPulse"
	_ring.mesh = mesh
	_ring.material_override = material
	_ring.position = Vector3(0.0, 0.18, 0.20)
	_ring.rotation_degrees.x = 90.0
	_ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_ring.visible = false
	add_child(_ring)
