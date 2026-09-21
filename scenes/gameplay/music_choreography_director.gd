extends Node

# Phase 9 music-to-body bridge. This node never moves the CharacterBody and never
# invokes gameplay actions. It only selects presentation phrases and preparation
# states on BallerinaVisualV1. The player still owns jump/tap/hold/swipe decisions.

const ACTIVATION_TIME := 30.0
const PREPARATION_ACTION := &"JUMP"
const SIGNATURE_MOVE := &"GRAND_JETE"
const SIGNATURE_MOVE_TIME := 53.0
const SIGNATURE_PRIMARY_CLASS := &"LARGE_TRAVELLING_LEAP"

@export var music_timeline: Node
@export var dancer: CharacterBody3D
@export var musicality: Node
@export var debug_label: Label
@export_file("*.json") var visual_score_path := "res://data/music/graceful_opening.visual_score_v0_1.json"

var _windows: Array = []
var _anchors: Array = []
var _reaction_lead := 0.75
var _visual: Node
var _last_role := &""
var _preparing_jump := false
var _preparing_signature := false


func _ready() -> void:
	if music_timeline == null or dancer == null or musicality == null:
		push_error("MusicChoreographyDirector requires MusicTimeline, Dancer and Musicality.")
		set_process(false)
		return
	_load_visual_score()
	if musicality.has_signal(&"accent_evaluated"):
		musicality.connect(&"accent_evaluated", Callable(self, "_on_accent_evaluated"))


func _process(_delta: float) -> void:
	_resolve_visual()
	if _visual == null:
		return

	var playback_time := float(music_timeline.call("get_playback_time"))
	if playback_time < ACTIVATION_TIME:
		_visual.call("set_music_expression_enabled", false)
		_show_debug("BASELINE")
		return

	_visual.call("set_music_expression_enabled", true)
	var window := _window_at(playback_time)
	var role := StringName(window.get("visual_intent", {}).get("phrase_role", "FLOW"))
	if role != _last_role:
		_last_role = role
		_visual.call("set_music_phrase_role", role)

	var preparing := _has_upcoming_required_jump(playback_time)
	if preparing != _preparing_jump:
		_preparing_jump = preparing
		_visual.call("set_music_action_preparation", PREPARATION_ACTION, preparing)

	var signature_preparing := _is_signature_preparation_active(playback_time)
	if signature_preparing != _preparing_signature:
		_preparing_signature = signature_preparing
		_visual.call(
			"set_signature_move_preparation",
			SIGNATURE_MOVE,
			signature_preparing
		)

	_show_debug("%s%s%s" % [
		String(role),
		" | PREP JUMP" if preparing else "",
		" | GRAND JETE" if signature_preparing else "",
	])


func _resolve_visual() -> void:
	if is_instance_valid(_visual):
		return
	_visual = dancer.get_node_or_null("BallerinaVisualV1")


func _load_visual_score() -> void:
	var file := FileAccess.open(visual_score_path, FileAccess.READ)
	if file == null:
		push_error("MusicChoreographyDirector could not open visual score: %s" % visual_score_path)
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("MusicChoreographyDirector visual score is invalid.")
		return
	var score: Dictionary = parsed
	_windows = score.get("windows", [])
	_anchors = score.get("event_anchors", [])
	_reaction_lead = float(
		score.get("playability_gate", {})
			.get("design_limits", {})
			.get("reaction_lead_seconds", 0.75)
	)


func _window_at(playback_time: float) -> Dictionary:
	for candidate: Variant in _windows:
		if typeof(candidate) != TYPE_DICTIONARY:
			continue
		var window: Dictionary = candidate
		if playback_time >= float(window.get("start", 0.0)) 		and playback_time < float(window.get("end", 0.0)):
			return window
	return {}


func _has_upcoming_required_jump(playback_time: float) -> bool:
	for candidate: Variant in _anchors:
		if typeof(candidate) != TYPE_DICTIONARY:
			continue
		var anchor: Dictionary = candidate
		var interaction: Dictionary = anchor.get("interaction", {})
		if not bool(interaction.get("required", false)):
			continue
		if StringName(interaction.get("candidate_action", "")) != PREPARATION_ACTION:
			continue
		var anchor_time := float(anchor.get("time", -1.0))
		if anchor_time < playback_time:
			continue
		if anchor_time - playback_time <= _reaction_lead:
			return true
		if anchor_time - playback_time > _reaction_lead:
			return false
	return false


func _is_signature_preparation_active(playback_time: float) -> bool:
	var remaining := SIGNATURE_MOVE_TIME - playback_time
	if remaining < 0.0 or remaining > _reaction_lead:
		return false
	for candidate: Variant in _anchors:
		if typeof(candidate) != TYPE_DICTIONARY:
			continue
		var anchor: Dictionary = candidate
		if absf(float(anchor.get("time", -1.0)) - SIGNATURE_MOVE_TIME) > 0.0001:
			continue
		if StringName(anchor.get("primary_class", "")) != SIGNATURE_PRIMARY_CLASS:
			return false
		var interaction: Dictionary = anchor.get("interaction", {})
		return (
			bool(interaction.get("required", false))
			and StringName(interaction.get("candidate_action", ""))
			== PREPARATION_ACTION
		)
	return false


func _on_accent_evaluated(classification: StringName, _delta: float, _marker_time: float) -> void:
	if classification == &"MISS":
		return
	_resolve_visual()
	if _visual != null:
		_visual.call("trigger_music_accent")


func _show_debug(value: String) -> void:
	if debug_label != null:
		debug_label.text = "CHOREO: %s" % value
