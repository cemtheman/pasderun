extends Node

const DANCER_VISUAL_SCRIPT := preload("res://scenes/gameplay/dancer_visual_motion_v5.gd")
const DANCER_TAP_FEEDBACK_SCRIPT := preload("res://scenes/gameplay/dancer_tap_feedback.gd")
const HUMANOID_LANDING_WINDOW := 0.22
const HUMANOID_LANDING_CLIP_FRACTION := 0.38

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

	# Prototype bridge: when an external rigged ballerina visual is already
	# parented under Dancer, keep the accepted Phase 7 visual/state machine
	# alive but hide its geometry. This lets the new skinned character inherit
	# gameplay motion without changing collision or dancer physics.
	var external_visual := dancer.get_node_or_null("BallerinaVisualV1")
	if external_visual is Node3D:
		visual.visible = false
		var external_player := external_visual.get_node_or_null("low_poly_girl/AnimationPlayer") as AnimationPlayer
		if external_player != null:
			_connect_ballerina_animation_bridge(visual, external_visual, external_player)
		else:
			push_warning("BallerinaVisualV1 found, but its AnimationPlayer is unavailable.")

	var capsule_visual := dancer.get_node_or_null("MeshInstance3D")
	if capsule_visual is GeometryInstance3D:
		capsule_visual.visible = false

	if dancer.get_node_or_null("TapVisualFeedback") == null:
		var tap_feedback := DANCER_TAP_FEEDBACK_SCRIPT.new()
		tap_feedback.name = "TapVisualFeedback"
		dancer.add_child(tap_feedback)



func _connect_ballerina_animation_bridge(
	visual: Node,
	external_visual: Node,
	player: AnimationPlayer
) -> void:
	if visual.get_meta("_ballerina_animation_bridge_connected", false):
		return

	visual.set_meta("_ballerina_animation_bridge_connected", true)
	visual.connect(
		"visual_state_changed",
		Callable(self, "_on_ballerina_visual_state_changed").bind(external_visual, player)
	)

	if visual.has_method("get_visual_state"):
		_on_ballerina_visual_state_changed(
			StringName(visual.call("get_visual_state")),
			external_visual,
			player
		)


func _on_ballerina_visual_state_changed(
	state: StringName,
	external_visual: Node,
	player: AnimationPlayer
) -> void:
	# Full-body retarget is now reserved for slow stage-presentation states.
	# Locomotion stays on the imported humanoid clips so spine/clavicle/wrist/toe
	# follow-through remains natural. Stumble/recovery are run clips with a late
	# procedural overlay applied by BallerinaVisualV1.
	if (
		external_visual != null
		and external_visual.has_method("handles_visual_state")
		and bool(external_visual.call("handles_visual_state", state))
	):
		player.stop()
		return

	match state:
		&"NEUTRAL":
			_play_ballerina_animation(player, &"idle", true, 1.0)
		&"STAGE_WALK":
			_play_ballerina_animation(player, &"walk", true, 1.0)
		&"JUMP":
			_play_ballerina_animation(player, &"jump_start", false, 1.0)
		&"AIRBORNE":
			_play_ballerina_animation(player, &"jump_falling", true, 1.0)
		&"LANDING":
			# Do not enter RUN's flight phase during the 0.22 s landing window.
			# Use the asset's grounded fast-walk cycle as a short contact bridge;
			# the next TRAVEL state blends naturally back to RUN.
			_play_grounded_landing_bridge(player)
		&"STUMBLE":
			_play_ballerina_animation(player, &"run", true, 0.94)
		&"RECOVERY":
			_play_ballerina_animation(player, &"run", true, 1.03)
		&"LOW_TRANSITION":
			_play_ballerina_animation(player, &"run", true, 0.92)
		&"TRAVEL", &"BALANCE", &"MUSIC_FLOW", &"MUSIC_BUILD", &"MUSIC_RELEASE", &"MUSIC_PULSE", &"MUSIC_CLIMAX", &"MUSIC_PREP", &"MUSIC_ACCENT":
			_play_ballerina_animation(player, &"run", true, 1.0)
		&"STAGE_READY", &"STAGE_BOW", &"STAGE_FINAL_BOW", &"STAGE_EXIT_TURN":
			# These are normally intercepted by handles_visual_state().
			_play_ballerina_animation(player, &"idle", true, 1.0)
		_:
			_play_ballerina_animation(player, &"idle", true, 1.0)


func _play_grounded_landing_bridge(player: AnimationPlayer) -> void:
	# Use only the CONTACT/ABSORPTION beginning of the native landing clip.
	# Playing the full clip produced the same-foot rebound seen in QA, while
	# switching directly to RUN selected a flight phase. Truncating the native
	# clip keeps its natural knee/hip compression and hands control back to RUN
	# before the rebound portion begins.
	if player.has_animation(&"jump_end"):
		var landing := player.get_animation(&"jump_end")
		if landing != null and landing.length > 0.0001:
			var source_segment := landing.length * HUMANOID_LANDING_CLIP_FRACTION
			var speed := source_segment / HUMANOID_LANDING_WINDOW
			_play_ballerina_animation(
				player,
				&"jump_end",
				false,
				maxf(speed, 0.10)
			)
			return

	if player.has_animation(&"walk_fast"):
		_play_ballerina_animation(player, &"walk_fast", true, 1.08)
		return
	if player.has_animation(&"walk"):
		_play_ballerina_animation(player, &"walk", true, 1.18)
		return

	# Last-resort fallback: stay grounded rather than selecting RUN while the
	# physics body is still in its landing-contact window.
	_play_ballerina_animation(player, &"idle", true, 1.0)


func _play_ballerina_animation(
	player: AnimationPlayer,
	animation_name: StringName,
	looped: bool,
	speed_scale: float = 1.0
) -> void:
	if not player.has_animation(animation_name):
		push_warning(
			"Ballerina animation '%s' is unavailable; keeping the current animation."
			% String(animation_name)
		)
		return

	var animation := player.get_animation(animation_name)
	if animation != null:
		animation.loop_mode = Animation.LOOP_LINEAR if looped else Animation.LOOP_NONE

	player.speed_scale = speed_scale
	if player.current_animation == String(animation_name) and player.is_playing():
		return

	player.play(animation_name, 0.10)
