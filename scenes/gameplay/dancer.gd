extends CharacterBody3D

signal tap_detected
signal stumble_started(reason: StringName)
signal locomotion_state_changed(state: StringName, reason: StringName)

enum LocomotionState {
	NORMAL,
	STUMBLE,
	RECOVERY,
}

const STUMBLE_DURATION := 0.24
const RECOVERY_DURATION := 0.62
const STUMBLE_SPEED_MULTIPLIER := 0.45
const RECOVERY_SPEED_MULTIPLIER := 1.21
const VALID_DROP_MINIMUM := 0.60
const MAX_TRAVERSABLE_STEP_HEIGHT := 0.45
const STEP_FORWARD_CLEARANCE := 0.16
const STEP_PROBE_BACKOFF := 0.08
const STUMBLE_VISUAL_TILT_RADIANS := 0.30
const STUMBLE_VISUAL_TILT_SPEED := 2.4
const RECOVERY_VISUAL_RETURN_SPEED := 0.65

# PAS DE RUN — DANCER CONTROLLER v0.4
#
# Working:
# - Auto-run
# - Gravity
# - Space debug jump
# - Mouse + touch gestures
# - Swipe Up -> Jump
# - Swipe Down -> Low Transition
# - Tap -> detected only
# - Hold -> Balance control
# - Left/Right -> detected only
# - Fall detection -> horizontal movement stops
# - BalanceArea -> Hold stabilizes dancer

@export var run_speed: float = 4.0
@export var jump_velocity: float = 6.0
@export var gravity: float = 18.0

@export_range(0.03, 0.25, 0.01)
var swipe_threshold_ratio: float = 0.10

@export_range(0.01, 0.10, 0.005)
var hold_slop_ratio: float = 0.035

@export var hold_threshold_ms: int = 350
@export var tap_max_ms: int = 280

@export var low_transition_duration: float = 0.55
@export var low_height: float = 1.0

# Dancer bu seviyenin altına düşerse ileri koşu durur.
@export var fall_limit_y: float = -3.0

# ---------------------------------------------------------
# BALANCE
# ---------------------------------------------------------

# Hold yapılmazsa yana kayma hızı.
@export var balance_drift_speed: float = 0.45

# Hold yapıldığında merkeze dönme kuvveti.
@export var balance_recenter_strength: float = 4.0

# Merkeze dönerken uygulanabilecek maksimum yatay hız.
@export var balance_max_recenter_speed: float = 1.25

@export var input_debug_label: Label

@onready var body_mesh: MeshInstance3D = $MeshInstance3D
@onready var body_collider: CollisionShape3D = $CollisionShape3D


# ---------------------------------------------------------
# INPUT STATE
# ---------------------------------------------------------

var press_start: Vector2 = Vector2.ZERO
var current_pointer: Vector2 = Vector2.ZERO
var press_started_ms: int = 0

var pressing: bool = false
var hold_triggered: bool = false

var using_touch: bool = false
var active_touch_index: int = -1


# ---------------------------------------------------------
# LOW TRANSITION STATE
# ---------------------------------------------------------

var in_low_transition: bool = false
var low_transition_timer: float = 0.0

var normal_collider_height: float = 0.0
var normal_collider_y: float = 0.0

var normal_mesh_scale: Vector3 = Vector3.ONE
var normal_mesh_y: float = 0.0
var normal_mesh_rotation_z: float = 0.0


# ---------------------------------------------------------
# FAIL STATE
# ---------------------------------------------------------

var has_fallen: bool = false


# ---------------------------------------------------------
# LOCOMOTION INTERRUPTION STATE
# ---------------------------------------------------------

var locomotion_state := LocomotionState.NORMAL
var last_stumble_reason: StringName = &""
var _locomotion_timer := 0.0
var _jump_in_progress := false
var _airborne_origin_y := 0.0


# ---------------------------------------------------------
# BALANCE STATE
# ---------------------------------------------------------

var in_balance_zone: bool = false

# Prototype'ta hep aynı tarafa doğru denge kaybı veriyoruz.
# İleride animasyon / müzik / route mantığıyla değişebilir.
var balance_drift_direction: float = 1.0


func _ready() -> void:

	var capsule: CapsuleShape3D = (
		body_collider.shape as CapsuleShape3D
	)

	if capsule == null:
		push_error(
			"Dancer CollisionShape3D üzerinde CapsuleShape3D bulunamadı."
		)
		return

	# Runtime sırasında collider yüksekliğini değiştireceğimiz için
	# resource'u duplicate ediyoruz.
	body_collider.shape = capsule.duplicate()

	capsule = (
		body_collider.shape as CapsuleShape3D
	)

	normal_collider_height = capsule.height
	normal_collider_y = body_collider.position.y

	normal_mesh_scale = body_mesh.scale
	normal_mesh_y = body_mesh.position.y
	normal_mesh_rotation_z = body_mesh.rotation.z


func _physics_process(delta: float) -> void:

	# ---------------------------------------------------------
	# FALL DETECTION
	# ---------------------------------------------------------

	if global_position.y < fall_limit_y:
		has_fallen = true

	if has_fallen:

		velocity.x = 0.0
		velocity.z = 0.0

		if not is_on_floor():
			velocity.y -= gravity * delta

		move_and_slide()
		return


	# ---------------------------------------------------------
	# AUTO-RUN
	# ---------------------------------------------------------

	_update_locomotion_state(delta)
	_update_locomotion_visual(delta)
	velocity.x = run_speed * _locomotion_speed_multiplier()


	# ---------------------------------------------------------
	# BALANCE
	# ---------------------------------------------------------

	if in_balance_zone:

		if _is_hold_active():

			# Hold aktif:
			# Karakter Z=0 merkez hattına doğru toparlanır.

			var recenter_velocity: float = (
				-global_position.z
				* balance_recenter_strength
			)

			velocity.z = clampf(
				recenter_velocity,
				-balance_max_recenter_speed,
				balance_max_recenter_speed
			)

		else:

			# Hold yok:
			# Karakter yavaşça beam'in dışına doğru kayar.

			velocity.z = (
				balance_drift_direction
				* balance_drift_speed
			)

	else:

		velocity.z = 0.0


	# ---------------------------------------------------------
	# GRAVITY
	# ---------------------------------------------------------

	if not is_on_floor():
		velocity.y -= gravity * delta


	# ---------------------------------------------------------
	# DESKTOP DEBUG JUMP
	# ---------------------------------------------------------

	if Input.is_action_just_pressed("jump"):
		_jump()
		_show_input("SPACE → JUMP")


	# ---------------------------------------------------------
	# LOW TRANSITION TIMER
	# ---------------------------------------------------------

	if in_low_transition:

		low_transition_timer -= delta

		if low_transition_timer <= 0.0:
			_end_low_transition()


	var was_on_floor := is_on_floor()
	var position_before_move := global_position
	move_and_slide()
	_handle_motion_outcome(was_on_floor, position_before_move, delta)


func _process(_delta: float) -> void:

	if not pressing:
		return

	if hold_triggered:
		return

	var elapsed: int = (
		Time.get_ticks_msec()
		- press_started_ms
	)

	var movement: float = (
		current_pointer.distance_to(press_start)
	)

	if (
		elapsed >= hold_threshold_ms
		and movement <= _hold_slop_px()
	):

		hold_triggered = true
		_show_input("HOLD")


func _input(event: InputEvent) -> void:

	# ---------------------------------------------------------
	# TOUCH
	# ---------------------------------------------------------

	if event is InputEventScreenTouch:

		if event.pressed:

			using_touch = true
			active_touch_index = event.index

			_begin_press(event.position)

		elif event.index == active_touch_index:

			_end_press(event.position)

			active_touch_index = -1
			using_touch = false


	# ---------------------------------------------------------
	# TOUCH DRAG
	# ---------------------------------------------------------

	elif event is InputEventScreenDrag:

		if event.index == active_touch_index:
			current_pointer = event.position


	# ---------------------------------------------------------
	# MOUSE BUTTON
	# ---------------------------------------------------------

	elif event is InputEventMouseButton:

		if (
			event.button_index == MOUSE_BUTTON_LEFT
			and not using_touch
		):

			if event.pressed:
				_begin_press(event.position)

			elif pressing:
				_end_press(event.position)


	# ---------------------------------------------------------
	# MOUSE MOTION
	# ---------------------------------------------------------

	elif event is InputEventMouseMotion:

		if pressing and not using_touch:
			current_pointer = event.position


func _begin_press(position: Vector2) -> void:

	press_start = position
	current_pointer = position

	press_started_ms = Time.get_ticks_msec()

	pressing = true
	hold_triggered = false


func _end_press(position: Vector2) -> void:

	if not pressing:
		return

	current_pointer = position

	var elapsed: int = (
		Time.get_ticks_msec()
		- press_started_ms
	)

	var gesture_delta: Vector2 = (
		position - press_start
	)

	var distance: float = gesture_delta.length()

	pressing = false


	# HOLD daha önce tetiklendiyse,
	# bırakma anında TAP/SWIPE üretme.
	if hold_triggered:

		hold_triggered = false

		if in_balance_zone:
			_show_input("HOLD RELEASE")

		return


	# ---------------------------------------------------------
	# SWIPE
	# ---------------------------------------------------------

	if distance >= _swipe_threshold_px():

		if abs(gesture_delta.y) > abs(gesture_delta.x):

			if gesture_delta.y < 0:

				_show_input("↑ SWIPE")
				_jump()

			else:

				_show_input("↓ SWIPE")
				_start_low_transition()

		else:

			if gesture_delta.x > 0:
				_show_input("→ SWIPE")

			else:
				_show_input("← SWIPE")

		return


	# ---------------------------------------------------------
	# TAP
	# ---------------------------------------------------------

	if elapsed <= tap_max_ms:
		_show_input("TAP")
		tap_detected.emit()


func _jump() -> void:

	if has_fallen:
		return

	if not is_on_floor():
		return

	if in_low_transition:
		return

	velocity.y = jump_velocity
	_jump_in_progress = true
	_airborne_origin_y = global_position.y


func get_locomotion_state() -> StringName:
	return StringName(LocomotionState.keys()[locomotion_state])


func reset_locomotion_state() -> void:
	locomotion_state = LocomotionState.NORMAL
	last_stumble_reason = &""
	_locomotion_timer = 0.0
	_jump_in_progress = false
	_airborne_origin_y = global_position.y
	body_mesh.rotation.z = normal_mesh_rotation_z
	locomotion_state_changed.emit(&"NORMAL", &"RESET")


func _update_locomotion_state(delta: float) -> void:
	if locomotion_state == LocomotionState.NORMAL:
		return
	_locomotion_timer -= delta
	if _locomotion_timer > 0.0:
		return
	if locomotion_state == LocomotionState.STUMBLE:
		locomotion_state = LocomotionState.RECOVERY
		_locomotion_timer = RECOVERY_DURATION
		locomotion_state_changed.emit(&"RECOVERY", last_stumble_reason)
		_show_input("RECOVERY")
	else:
		locomotion_state = LocomotionState.NORMAL
		_locomotion_timer = 0.0
		locomotion_state_changed.emit(&"NORMAL", last_stumble_reason)
		_show_input("NORMAL")


func _update_locomotion_visual(delta: float) -> void:
	var target_rotation_z := normal_mesh_rotation_z
	var rotation_speed := RECOVERY_VISUAL_RETURN_SPEED
	if locomotion_state == LocomotionState.STUMBLE:
		target_rotation_z = normal_mesh_rotation_z - STUMBLE_VISUAL_TILT_RADIANS
		rotation_speed = STUMBLE_VISUAL_TILT_SPEED
	body_mesh.rotation.z = move_toward(
		body_mesh.rotation.z,
		target_rotation_z,
		rotation_speed * delta
	)


func _locomotion_speed_multiplier() -> float:
	if locomotion_state == LocomotionState.STUMBLE:
		return STUMBLE_SPEED_MULTIPLIER
	if locomotion_state == LocomotionState.RECOVERY:
		return RECOVERY_SPEED_MULTIPLIER
	return 1.0


func _handle_motion_outcome(
	was_on_floor: bool,
	position_before_move: Vector3,
	delta: float
) -> void:
	if was_on_floor and not is_on_floor():
		_airborne_origin_y = position_before_move.y

	var hit_forward_edge := false
	for collision_index in get_slide_collision_count():
		var collision := get_slide_collision(collision_index)
		var normal := collision.get_normal()
		if normal.x < -0.55 and absf(normal.y) < 0.45:
			hit_forward_edge = true
			break

	# Capsule/box contacts at a platform lip can report a diagonal normal rather
	# than a clean horizontal wall normal.  Runtime acceptance therefore cannot
	# rely on collision-normal classification alone: if a grounded auto-run frame
	# makes materially less forward progress than requested, treat that as a
	# candidate traversable step and let the clearance probe decide.
	var intended_forward := (
		run_speed
		* _locomotion_speed_multiplier()
		* delta
	)
	var actual_forward := maxf(
		global_position.x - position_before_move.x,
		0.0
	)
	var stalled_forward := (
		was_on_floor
		and intended_forward > 0.001
		and actual_forward < intended_forward * 0.35
	)

	if was_on_floor and (hit_forward_edge or stalled_forward):
		if _attempt_small_step(delta):
			_trigger_stumble(&"SMALL_STEP")
	elif hit_forward_edge:
		if not was_on_floor or _jump_in_progress:
			_trigger_stumble(&"PLATFORM_EDGE")

	if not was_on_floor and is_on_floor():
		var drop_distance := _airborne_origin_y - global_position.y
		if not _jump_in_progress and drop_distance >= VALID_DROP_MINIMUM:
			_trigger_stumble(&"LOWER_ROUTE_DROP")
		_jump_in_progress = false


func _attempt_small_step(delta: float) -> bool:
	var probe_transform := global_transform
	probe_transform.origin.x -= STEP_PROBE_BACKOFF
	var upward_motion := Vector3.UP * MAX_TRAVERSABLE_STEP_HEIGHT
	if test_move(probe_transform, upward_motion):
		return false

	# Perform the forward clearance test from the backed-off transform as well.
	# Starting the raised probe from the exact wall-contact transform can keep the
	# capsule inside the contact margin and make a valid 0.25 m step look blocked.
	var raised_transform := probe_transform
	raised_transform.origin.y += MAX_TRAVERSABLE_STEP_HEIGHT
	var desired_forward := maxf(
		maxf(run_speed * delta, STEP_FORWARD_CLEARANCE),
		STEP_FORWARD_CLEARANCE
	)
	var forward_motion := Vector3(
		STEP_PROBE_BACKOFF + desired_forward,
		0.0,
		0.0
	)
	if test_move(raised_transform, forward_motion):
		return false

	global_transform = raised_transform
	move_and_collide(forward_motion)

	# Settle immediately onto the first playable surface below the raised probe.
	# This avoids a one-frame hover and makes the step read as a stumble-through
	# rather than a miniature jump.
	move_and_collide(Vector3.DOWN * MAX_TRAVERSABLE_STEP_HEIGHT)
	velocity.x = run_speed * STUMBLE_SPEED_MULTIPLIER
	return true


func _trigger_stumble(reason: StringName) -> void:
	if has_fallen or locomotion_state != LocomotionState.NORMAL:
		return
	locomotion_state = LocomotionState.STUMBLE
	last_stumble_reason = reason
	_locomotion_timer = STUMBLE_DURATION
	stumble_started.emit(reason)
	locomotion_state_changed.emit(&"STUMBLE", reason)
	_show_input("STUMBLE: %s" % reason)


func _start_low_transition() -> void:

	if has_fallen:
		return

	if not is_on_floor():
		return

	if in_low_transition:
		return

	var capsule: CapsuleShape3D = (
		body_collider.shape as CapsuleShape3D
	)

	if capsule == null:
		return

	var minimum_height: float = (
		capsule.radius * 2.0
	)

	var target_height: float = maxf(
		low_height,
		minimum_height
	)

	var height_change: float = (
		normal_collider_height
		- target_height
	)

	if height_change <= 0.0:
		return

	in_low_transition = true
	low_transition_timer = low_transition_duration


	# ---------------------------------------------------------
	# COLLIDER
	# ---------------------------------------------------------

	capsule.height = target_height

	body_collider.position.y = (
		normal_collider_y
		- height_change * 0.5
	)


	# ---------------------------------------------------------
	# PLACEHOLDER VISUAL
	# ---------------------------------------------------------

	var height_ratio: float = (
		target_height
		/ normal_collider_height
	)

	body_mesh.scale = Vector3(
		normal_mesh_scale.x,
		normal_mesh_scale.y * height_ratio,
		normal_mesh_scale.z
	)

	body_mesh.position.y = (
		normal_mesh_y
		- height_change * 0.5
	)


func _end_low_transition() -> void:

	if not in_low_transition:
		return

	var capsule: CapsuleShape3D = (
		body_collider.shape as CapsuleShape3D
	)

	if capsule == null:
		return

	capsule.height = normal_collider_height

	body_collider.position.y = (
		normal_collider_y
	)

	body_mesh.scale = normal_mesh_scale

	body_mesh.position.y = (
		normal_mesh_y
	)

	in_low_transition = false
	low_transition_timer = 0.0


# =========================================================
# BALANCE AREA API
# =========================================================

# BalanceArea script'i bu fonksiyonu çağırır.
func enter_balance_zone() -> void:

	if has_fallen:
		return

	in_balance_zone = true

	# Prototype için dışarı doğru sabit yön.
	# Z=0'ın hangi tarafında olduğumuza göre yönü koruyoruz.
	if global_position.z < 0.0:
		balance_drift_direction = -1.0
	else:
		balance_drift_direction = 1.0

	_show_input("BALANCE → HOLD")


# BalanceArea'dan çıkınca normal koşuya dön.
func exit_balance_zone() -> void:

	in_balance_zone = false
	velocity.z = 0.0

	_show_input("BALANCE EXIT")


func _is_hold_active() -> bool:

	return (
		pressing
		and hold_triggered
	)


func _swipe_threshold_px() -> float:

	var screen_size: Vector2 = (
		get_viewport()
		.get_visible_rect()
		.size
	)

	return (
		minf(
			screen_size.x,
			screen_size.y
		)
		* swipe_threshold_ratio
	)


func _hold_slop_px() -> float:

	var screen_size: Vector2 = (
		get_viewport()
		.get_visible_rect()
		.size
	)

	return (
		minf(
			screen_size.x,
			screen_size.y
		)
		* hold_slop_ratio
	)


func _show_input(text: String) -> void:

	if input_debug_label != null:
		input_debug_label.text = (
			"INPUT: " + text
		)

	print(
		"INPUT: ",
		text
	)
