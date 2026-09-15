extends CharacterBody3D

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


# ---------------------------------------------------------
# FAIL STATE
# ---------------------------------------------------------

var has_fallen: bool = false


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

	velocity.x = run_speed


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


	move_and_slide()


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


func _jump() -> void:

	if has_fallen:
		return

	if not is_on_floor():
		return

	if in_low_transition:
		return

	velocity.y = jump_velocity


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
