extends Node3D

# Tap feedback has two presentation paths:
# - native: the accepted short gold 3D ring pulse
# - Web: no 3D feedback geometry at all. Toggling a MeshInstance3D into the
#   render list caused a visible browser stall. Web therefore uses only a short
#   transform pulse on the already-rendered imported ballerina visual.
# Gameplay Tap, musicality and Flow remain untouched.
const PULSE_DURATION := 0.18
const PULSE_START_SCALE := 0.72
const PULSE_END_SCALE := 1.42
const WEB_PULSE_DURATION := 0.14
const WEB_SCALE_XZ_AMOUNT := 0.035
const WEB_SCALE_Y_AMOUNT := 0.075

var dancer: CharacterBody3D
var _ring: MeshInstance3D
var _remaining := 0.0
var _web_mode := false
var _web_visual: Node3D
var _web_base_scale := Vector3.ONE


func _ready() -> void:
	dancer = get_parent() as CharacterBody3D
	if dancer == null or not dancer.has_signal(&"tap_detected"):
		push_error("DancerTapFeedback requires Dancer.tap_detected.")
		queue_free()
		return

	_web_mode = OS.has_feature("web")
	if _web_mode:
		_web_visual = dancer.get_node_or_null("BallerinaVisualV1") as Node3D
		if _web_visual != null:
			_web_base_scale = _web_visual.scale
	else:
		_build_ring()

	dancer.connect(&"tap_detected", Callable(self, "_on_tap_detected"))
	set_process(false)


func _process(delta: float) -> void:
	_remaining = maxf(_remaining - delta, 0.0)
	if _web_mode:
		_update_web_pulse()
		return

	var progress := 1.0 - (_remaining / PULSE_DURATION)
	var scale_value := lerpf(PULSE_START_SCALE, PULSE_END_SCALE, progress)
	_ring.scale = Vector3.ONE * scale_value
	if _remaining <= 0.0:
		_ring.visible = false
		set_process(false)


func _on_tap_detected() -> void:
	if _web_mode:
		if _web_visual == null:
			return
		_remaining = WEB_PULSE_DURATION
		set_process(true)
		return

	_remaining = PULSE_DURATION
	_ring.visible = true
	_ring.scale = Vector3.ONE * PULSE_START_SCALE
	set_process(true)


func _update_web_pulse() -> void:
	if _web_visual == null:
		set_process(false)
		return
	var progress := 1.0 - (_remaining / WEB_PULSE_DURATION)
	var pulse := sin(progress * PI)
	_web_visual.scale = Vector3(
		_web_base_scale.x * (1.0 + pulse * WEB_SCALE_XZ_AMOUNT),
		_web_base_scale.y * (1.0 + pulse * WEB_SCALE_Y_AMOUNT),
		_web_base_scale.z * (1.0 + pulse * WEB_SCALE_XZ_AMOUNT)
	)
	if _remaining <= 0.0:
		_web_visual.scale = _web_base_scale
		set_process(false)


func _build_ring() -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.94, 0.80, 0.48, 1.0)
	material.roughness = 0.55

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
