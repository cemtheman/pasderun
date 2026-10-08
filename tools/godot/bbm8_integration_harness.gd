extends SceneTree
const MAIN := "res://scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"
var runtime: Node3D
var gate: Node
var visual: Node3D
var dancer: CharacterBody3D
var skeleton: Skeleton3D
var audio: AudioStreamPlayer
var failures: Array = []
var checks: Array = []
var completions: Array = []
var observations: Array = []
var views: Dictionary = {}
var output := ""
var mode := "capture"
var frame := 0

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):
			output = arg.trim_prefix("--output=")
		if arg.begins_with("--mode="):
			mode = arg.trim_prefix("--mode=")
	call_deferred("run")

func check(ok: bool, name: String) -> void:
	checks.append({"name": name, "pass": ok})
	if not ok:
		failures.append(name)
	print("BBM8_TEST ", name, " ", "PASS" if ok else "FAIL")

func setup() -> void:
	runtime = load(MAIN).instantiate()
	if mode == "baseline":
		var original_gate: Node = runtime.get_node("RuntimeStartGate")
		var references: Dictionary = {}
		for key in ["dancer","music_root","audio_player","flow_tracker","tap_timing_debug","accent_runtime_trace","overlay","entrance_target_x","entrance_walk_distance","entrance_speed","bow_duration"]:
			references[key] = original_gate.get(key)
		original_gate.set_script(load("res://tools/godot/baseline/gate.gd"))
		for key in references:
			original_gate.set(key, references[key])
		runtime.get_node("Dancer/BallerinaVisualV1").set_script(load("res://tools/godot/baseline/controller.gd"))
	root.add_child(runtime)
	current_scene = runtime
	gate = runtime.get_node("RuntimeStartGate")
	dancer = runtime.get_node("Dancer")
	visual = dancer.get_node("BallerinaVisualV1")
	skeleton = visual.get_node("low_poly_girl/Rig/Skeleton3D")
	audio = gate.audio_player
	completions.clear()
	if mode not in ["baseline", "regression"]:
		visual.bbm8_finished.connect(func(token, outcome): completions.append({"token": token, "outcome": outcome}))
		gate.bbm8_phrase_enabled = true
	gate.set_process_input(false)
	var ticks := 0
	while gate._prelude_state != gate.PreludeState.READY and ticks < 600:
		await RenderingServer.frame_post_draw
		ticks += 1
	for i in 24:
		await RenderingServer.frame_post_draw
	check(gate._prelude_state == gate.PreludeState.READY and dancer.is_on_floor(), "real_main_scene_ready_grounded")

func tick(count: int) -> void:
	for i in count:
		await RenderingServer.frame_post_draw

func start_event() -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_ENTER
	event.pressed = true
	gate._input(event)

func finished(timeout := 850) -> void:
	for i in timeout:
		await RenderingServer.frame_post_draw
		if not visual.get_bbm8_state().busy:
			return
	check(false, "lifecycle_timeout")

func run() -> void:
	if output.is_empty():
		push_error("BBM8 harness requires an explicit fresh output directory")
		quit(2)
		return
	DirAccess.make_dir_recursive_absolute(output)
	await setup()
	if mode in ["baseline", "regression"]:
		await default_gameplay_trace()
	elif mode == "tests":
		await focused_tests()
	else:
		await lifecycle_capture()
	var report := {"mode": mode, "engine": Engine.get_version_info(), "renderer": RenderingServer.get_current_rendering_method(), "device": RenderingServer.get_video_adapter_name(), "checks": checks, "failures": failures, "completions": completions, "observations": observations, "status": "CONTROL_TEST_PASS" if failures.is_empty() else "FAIL", "geometry_visual_acceptance": "PENDING"}
	var f := FileAccess.open(output.path_join("runtime.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report))
	print("BBM8_HARNESS_DONE ", report.status)
	quit(0 if failures.is_empty() else 1)

func focused_tests() -> void:
	gate.bbm8_phrase_enabled = false
	check(not gate.request_bbm8_phrase(), "default_off_request_rejected")
	gate.bbm8_phrase_enabled = true
	dancer.locomotion_state = dancer.LocomotionState.STUMBLE
	check(not gate.request_bbm8_phrase(), "stumble_precondition_rejected")
	dancer.locomotion_state = dancer.LocomotionState.NORMAL
	dancer.in_low_transition = true
	check(not gate.request_bbm8_phrase(), "low_transition_precondition_rejected")
	dancer.in_low_transition = false
	dancer.in_balance_zone = true
	check(not gate.request_bbm8_phrase(), "balance_precondition_rejected")
	dancer.in_balance_zone = false
	dancer.stage_ending_mode = true
	check(not gate.request_bbm8_phrase(), "closing_precondition_rejected")
	dancer.stage_ending_mode = false
	dancer.velocity.x = 0.1
	check(not gate.request_bbm8_phrase(), "moving_precondition_rejected")
	dancer.velocity.x = 0.0
	check(gate.request_bbm8_phrase(), "entry_request_accepted")
	check(not gate.request_bbm8_phrase(), "duplicate_request_rejected")
	await tick(30)
	var clock: float = visual.get_bbm8_state().elapsed
	paused = true
	await tick(12)
	check(is_equal_approx(clock, visual.get_bbm8_state().elapsed), "pause_freezes_phrase_clock")
	paused = false
	gate.cancel_bbm8_phrase()
	check(visual.get_bbm8_state().busy, "cancel_preserves_orderly_closure")
	await finished()
	check(completions.size() == 1 and completions[0].outcome == &"CANCELLED_AFTER_CLOSURE", "cancel_completion_exactly_once")
	print("BBM8_CANCEL_DEBUG ", gate._prelude_state, " started=", gate._started, " active=", gate._bbm8_active_token, " audio=", audio.playing, " queued=", gate._bbm8_start_queued)
	check(gate._prelude_state == gate.PreludeState.READY and not audio.playing, "cancel_restores_ready_silent")
	check(gate.request_bbm8_phrase(), "second_request_new_token")
	await tick(15)
	start_event()
	check(gate._bbm8_start_queued and audio.stream_paused, "start_gesture_queues_and_unlocks_paused_audio")
	gate.reset_bbm8_phrase()
	await tick(2)
	check(not visual.get_bbm8_state().busy and not gate._bbm8_start_queued and not gate._started and not audio.playing, "reset_invalidates_pending_start_and_token")
	check(gate.request_bbm8_phrase(), "request_after_reset")
	await tick(5)
	dancer.has_fallen = true
	await tick(2)
	check(not visual.get_bbm8_state().busy and completions[-1].outcome == &"GROUNDING_LOST", "fall_observable_abort_releases_authority")
	dancer.has_fallen = false
	visual.set_stage_presentation_state(&"READY")
	await tick(30)
	check(gate.request_bbm8_phrase(), "request_after_abort")
	await tick(20)
	root.get_texture().get_image().save_png(output.path_join("before_ground_loss.png"))
	var collision_mask := dancer.collision_mask
	# Fault injection removes support collision; Dancer still integrates gravity.
	# No position write or second physics driver is introduced.
	dancer.collision_mask = 0
	await tick(2)
	check(not dancer.is_on_floor() and not visual.get_bbm8_state().busy and completions[-1].outcome == &"GROUNDING_LOST", "actual_ground_loss_observable_abort")
	root.get_texture().get_image().save_png(output.path_join("after_ground_loss.png"))
	dancer.collision_mask = collision_mask
	await tick(30)
	check(dancer.is_on_floor(), "physics_regains_ground_after_fault")
	visual.set_stage_presentation_state(&"READY")
	await tick(30)
	check(gate.request_bbm8_phrase(), "request_after_ground_recovery")
	await tick(5)
	visual.set_stage_presentation_state(&"EXIT_TURN")
	check(not visual.get_bbm8_state().busy and completions[-1].outcome == &"STAGE_AUTHORITY_CHANGED", "stage_change_explicit_abort")
	visual.set_stage_presentation_state(&"READY")
	await tick(30)
	check(gate.request_bbm8_phrase(), "final_request")
	await tick(60)
	start_event()
	await finished()
	await tick(60)
	check(gate._prelude_state == gate.PreludeState.STARTED and dancer.velocity.x > 0.1, "queued_start_resumes_original_locomotion")
	check(audio.playing and not audio.stream_paused and audio.get_playback_position() > 0.0, "original_music_release_after_exit_turn")

func lifecycle_capture() -> void:
	if mode != "geometry":
		create_views()
	await tick(2)
	if mode != "geometry":
		capture_images("before_entry")
	check(gate.request_bbm8_phrase(), "capture_request")
	var body_start := dancer.global_position
	var model_start: Transform3D = visual.get_node("low_poly_girl").transform
	var animation: AnimationPlayer = visual.get_node("low_poly_girl/AnimationPlayer")
	var animation_position := animation.current_animation_position
	var queued := false
	var resumed_ticks := 0
	for i in 900:
		await RenderingServer.frame_post_draw
		frame += 1
		var state: Dictionary = visual.get_bbm8_state()
		if state.busy and float(state.elapsed) >= 2.5 and not queued:
			start_event()
			queued = true
		var phase := String(state.phase) if state.busy else ("EXIT_TURN" if gate._prelude_state == gate.PreludeState.EXIT_TURN else ("GAMEPLAY" if gate._started else "READY"))
		if state.busy:
			if dancer.global_position.distance_to(body_start) > 0.0001:
				check(false, "body_root_boundary")
			if not is_equal_approx(animation.current_animation_position, animation_position):
				check(false, "native_animation_advanced_behind_phrase")
			if not visual.get_node("low_poly_girl").transform.is_equal_approx(model_start):
				check(false, "model_root_changed_during_phrase")
		var bones: Array = []
		for b in skeleton.get_bone_count():
			var t := skeleton.get_bone_global_pose(b)
			var q := t.basis.get_rotation_quaternion()
			check_finite(t)
			bones.append([q.x, q.y, q.z, q.w, t.origin.x, t.origin.y, t.origin.z])
		observations.append({"frame": frame, "phase": phase, "elapsed": state.elapsed, "body": [dancer.position.x,dancer.position.y,dancer.position.z], "bones": bones, "grounded": dancer.is_on_floor(), "audio_time": audio.get_playback_position(), "audio_paused": audio.stream_paused, "contact_roles": state.get("contact_roles", {}), "entry_seconds": state.get("entry_seconds", 2.4), "skeleton_world": encode_transform(skeleton.global_transform)})
		update_views()
		if mode != "geometry" and frame % 6 == 0:
			capture_images("%04d_%s" % [frame, phase])
		if phase == "GAMEPLAY":
			resumed_ticks += 1
			if resumed_ticks >= 60:
				break
	check(completions.size() == 1 and completions[0].outcome == &"COMPLETED", "capture_single_completion")
	check(resumed_ticks >= 60 and dancer.velocity.x > 0.1 and audio.playing and not audio.stream_paused, "capture_gameplay_music_recovered")
	check(animation.is_playing(), "native_animation_resumed")

func check_finite(t: Transform3D) -> void:
	if not t.origin.is_finite() or not t.basis.x.is_finite() or not t.basis.y.is_finite() or not t.basis.z.is_finite():
		check(false, "finite_runtime_transform")

func create_views() -> void:
	for view in ["front", "side", "three_quarter"]:
		DirAccess.make_dir_recursive_absolute(output.path_join(view))
		var viewport := SubViewport.new()
		viewport.size = Vector2i(480, 640)
		viewport.world_3d = runtime.get_world_3d()
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(viewport)
		var camera := Camera3D.new()
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		camera.size = 2.25
		viewport.add_child(camera)
		camera.make_current()
		views[view] = {"viewport": viewport, "camera": camera}
	DirAccess.make_dir_recursive_absolute(output.path_join("gameplay"))
	update_views()

func update_views() -> void:
	var target := dancer.global_position + Vector3(0,0.1,0)
	for view in views:
		var direction := Vector3(0,0,1) if view == "front" else (Vector3(1,0,0) if view == "side" else Vector3(1,0,1).normalized())
		var camera: Camera3D = views[view].camera
		camera.global_position = target + direction * 5.0
		camera.look_at(target, Vector3.UP)

func capture_images(label: String) -> void:
	var err := root.get_texture().get_image().save_png(output.path_join("gameplay/" + label + ".png"))
	if err != OK:
		check(false, "capture_write")
	for view in views:
		err = views[view].viewport.get_texture().get_image().save_png(output.path_join(view + "/" + label + ".png"))
		if err != OK:
			check(false, "diagnostic_capture_write")



func encode_transform(t: Transform3D) -> Array:
	return [[t.basis.x.x,t.basis.x.y,t.basis.x.z], [t.basis.y.x,t.basis.y.y,t.basis.y.z], [t.basis.z.x,t.basis.z.y,t.basis.z.z], [t.origin.x,t.origin.y,t.origin.z]]


func default_gameplay_trace() -> void:
	# Identical real main scene and standard start path with feature default OFF.
	if mode == "regression":
		check(not gate.bbm8_phrase_enabled, "default_feature_off")
	start_event()
	for i in 120:
		await RenderingServer.frame_post_draw
		var bones: Array = []
		for b in skeleton.get_bone_count():
			var t := skeleton.get_bone_global_pose(b)
			var q := t.basis.get_rotation_quaternion()
			bones.append([q.x,q.y,q.z,q.w,t.origin.x,t.origin.y,t.origin.z])
		observations.append({"frame": i, "body": [dancer.position.x,dancer.position.y,dancer.position.z], "bones": bones, "state": visual.get_visual_state(), "audio_playing": audio.playing, "audio_paused": audio.stream_paused, "stage_entrance": dancer.stage_entrance_mode})
	check(gate._started and not dancer.stage_entrance_mode and dancer.velocity.x > 0.1 and audio.playing and not audio.stream_paused, "default_original_start_and_music")


