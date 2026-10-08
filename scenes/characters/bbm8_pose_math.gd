extends RefCounted
# Pure pose math only. HumanoidMotionController remains the sole pose writer.
const PATH := "res://assets/bbm8/clear6s_runtime_candidate.json"
var data: Dictionary = {}
var frames: Array = []
var indices: Array[int] = []
var ready: Array[Transform3D] = []
var ready_wrist: Dictionary = {}
var last_wrist: Dictionary = {}
var contact_roles := {"left": "SUPPORT", "right": "SUPPORT"}
var elapsed := 0.0
var entry_seconds := 2.4
var exit_seconds := 2.4
var phase := &"ENTRY"
var model_transform: Transform3D

func bind(skeleton: Skeleton3D, model: Node3D) -> bool:
	data = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	if data.is_empty() or data.get("schema") != 2:
		return false
	if FileAccess.get_sha256("res://assets/characters/low_poly_girl/low_poly_girl .glb") != data.source_glb_sha256:
		return false
	if FileAccess.get_sha256("res://build/visual_validation/BBM-7/candidate-01/report.json") != data.accepted_report_sha256:
		return false
	frames = data.frames
	for row in data.bones:
		var index := skeleton.find_bone(row.name)
		if index < 0 or skeleton.get_bone_parent(index) != int(row.parent):
			return false
		var rest := skeleton.get_bone_global_rest(index)
		if (rest.origin - vec(row.godot_rest[3])).length() > 0.00001:
			return false
		var expected_rest := Basis(vec(row.godot_rest[0]), vec(row.godot_rest[1]), vec(row.godot_rest[2]))
		for col in 3:
			if (rest.basis[col] - expected_rest[col]).length() > 0.00001:
				return false
		indices.append(index)
		ready.append(skeleton.get_bone_global_pose(index))
	model_transform = model.transform
	for side in ["left", "right"]:
		ready_wrist[side] = decode_wrist(ready, side)
		# Project only the opt-in bridge onto the existing preferred wrist DOFs.
		# The original READY snapshot is restored on release; default READY is unchanged.
		ready_wrist[side].flexion_extension_deg = clampf(ready_wrist[side].flexion_extension_deg, -55.0, 55.0)
		ready_wrist[side].radial_ulnar_deviation_deg = clampf(ready_wrist[side].radial_ulnar_deviation_deg, -25.0, 20.0)
	return true

func sample(clock: float) -> Array[Transform3D]:
	var result: Array[Transform3D] = []
	var lo := 0
	while lo + 1 < frames.size() and float(frames[lo + 1].time) * 6.0 <= clock:
		lo += 1
	var hi := mini(lo + 1, frames.size() - 1)
	var a := float(frames[lo].time) * 6.0
	var b := float(frames[hi].time) * 6.0
	var w := clampf((clock - a) / maxf(b - a, 0.00000001), 0.0, 1.0)
	var source_a := decode_frame(frames[lo])
	var source_b := decode_frame(frames[hi])
	result = blend_local(source_a, source_b, w)
	last_wrist.clear()
	for side in ["left", "right"]:
		var wa: Dictionary = frames[lo].wrist[side]
		var wb: Dictionary = frames[hi].wrist[side]
		var values := Vector2(lerpf(wa.flexion_extension_deg, wb.flexion_extension_deg, w), lerpf(wa.radial_ulnar_deviation_deg, wb.radial_ulnar_deviation_deg, w))
		reconstruct_wrist(result, side, values)
		last_wrist[side] = [values.x, values.y]
	return result

func advance(delta: float) -> Array[Transform3D]:
	elapsed += delta
	var poses: Array[Transform3D]
	if elapsed < entry_seconds:
		phase = &"ENTRY"
		var target := sample(0.0)
		var u := jerk(elapsed / entry_seconds)
		poses = step_bridge(ready, target, elapsed / entry_seconds)
		bridge_wrists(poses, ready_wrist, frames[0].wrist, u)
	elif elapsed <= entry_seconds + 6.0:
		phase = &"ACTIVE"
		contact_roles = {"left": "SUPPORT", "right": "SUPPORT"}
		var t := (elapsed - entry_seconds) / 6.0
		if t >= 0.48 and t <= 0.56:
			contact_roles.right = "TOUCH"
		poses = sample(elapsed - entry_seconds)
	elif elapsed < entry_seconds + 6.0 + exit_seconds:
		phase = &"EXIT"
		var target := sample(6.0)
		var u := jerk((elapsed - entry_seconds - 6.0) / exit_seconds)
		poses = step_bridge(target, ready, (elapsed - entry_seconds - 6.0) / exit_seconds)
		bridge_wrists(poses, frames[-1].wrist, ready_wrist, u)
	else:
		phase = &"COMPLETE"
		poses = ready.duplicate()
	return poses

func blend_local(a: Array[Transform3D], b: Array[Transform3D], w: float) -> Array[Transform3D]:
	var result: Array[Transform3D] = []
	for i in indices.size():
		var parent := int(data.bones[i].parent)
		var la := a[i] if parent < 0 else a[parent].affine_inverse() * a[i]
		var lb := b[i] if parent < 0 else b[parent].affine_inverse() * b[i]
		var q := la.basis.get_rotation_quaternion().slerp(lb.basis.get_rotation_quaternion(), w)
		# Parent-first FK preserves segment lengths; only pelvis has translation intent.
		var origin := la.origin.lerp(lb.origin, w) if parent < 0 else la.origin
		var local := Transform3D(Basis(q), origin)
		result.append(local if parent < 0 else result[parent] * local)
	return result

func bridge_wrists(poses: Array[Transform3D], a: Dictionary, b: Dictionary, w: float) -> void:
	for side in ["left", "right"]:
		var values := Vector2(lerpf(float(a[side].flexion_extension_deg), float(b[side].flexion_extension_deg), w), lerpf(float(a[side].radial_ulnar_deviation_deg), float(b[side].radial_ulnar_deviation_deg), w))
		reconstruct_wrist(poses, side, values)
		last_wrist[side] = [values.x, values.y]

func reconstruct_wrist(poses: Array[Transform3D], side: String, values: Vector2) -> void:
	var record: Dictionary = data.wrists[side]
	var parent: Dictionary = record.parent
	var hand: Dictionary = record.hand
	var p := matrix(parent.left) * poses[int(parent.bone)].basis * matrix(parent.right)
	var canonical := p * matrix(record.rest_local) * Basis(Vector3.RIGHT, deg_to_rad(values.x)) * Basis(Vector3.BACK, deg_to_rad(values.y))
	var index := int(hand.bone)
	var before := poses[index]
	poses[index].basis = (matrix(hand.left).inverse() * canonical * matrix(hand.right).inverse()).orthonormalized()
	# Fingers follow the reconstructed hand, never the interpolated axial hand roll.
	var adjustment := poses[index] * before.affine_inverse()
	for i in range(index + 1, poses.size()):
		var parent_index := int(data.bones[i].parent)
		while parent_index >= 0:
			if parent_index == index:
				poses[i] = adjustment * poses[i]
				break
			parent_index = int(data.bones[parent_index].parent)

func decode_wrist(poses: Array[Transform3D], side: String) -> Dictionary:
	var r: Dictionary = data.wrists[side]
	var p := matrix(r.parent.left) * poses[int(r.parent.bone)].basis * matrix(r.parent.right)
	var h := matrix(r.hand.left) * poses[int(r.hand.bone)].basis * matrix(r.hand.right)
	var d := matrix(r.rest_local).inverse() * p.inverse() * h
	var flex := rad_to_deg(atan2(-d.z.y, d.z.z))
	var radial := rad_to_deg(atan2(-d.y.x, d.x.x))
	var reconstructed := Basis(Vector3.RIGHT, deg_to_rad(flex)) * Basis(Vector3.BACK, deg_to_rad(radial))
	var error := 0.0
	for col in 3:
		for row in 3:
			error = maxf(error, absf(d[col][row] - reconstructed[col][row]))
	return {"flexion_extension_deg": flex, "radial_ulnar_deviation_deg": radial, "reconstruction_error": error}

func decode_frame(frame: Dictionary) -> Array[Transform3D]:
	var result: Array[Transform3D] = []
	for p in frame.poses:
		result.append(Transform3D(Basis(Quaternion(p[0], p[1], p[2], p[3]).normalized()), Vector3(p[4], p[5], p[6])))
	return result

static func matrix(rows: Array) -> Basis:
	return Basis(Vector3(rows[0][0], rows[1][0], rows[2][0]), Vector3(rows[0][1], rows[1][1], rows[2][1]), Vector3(rows[0][2], rows[1][2], rows[2][2]))
static func vec(v: Array) -> Vector3:
	return Vector3(v[0], v[1], v[2])
static func jerk(u: float) -> float:
	u = clampf(u, 0.0, 1.0)
	return u * u * u * (10.0 + u * (-15.0 + 6.0 * u))


func step_bridge(a: Array[Transform3D], b: Array[Transform3D], u: float) -> Array[Transform3D]:
	# Explicit support transfer -> swing placement -> transfer -> other placement.
	# The failed planted slide is replaced by observable contact-role changes.
	var poses := blend_local(a, b, jerk(u))
	contact_roles = {"left": "SUPPORT", "right": "SUPPORT"}
	var lateral := 0.0
	# Measured endpoint contact polygons require different support transfers for
	# READY's wide parallel feet and BBM's turned-out closed-first stance.
	var first_support := 0.16 if phase == &"ENTRY" else 0.105
	var second_support := -0.125 if phase == &"ENTRY" else -0.16
	if u < 0.2:
		lateral = first_support * jerk(u / 0.2)
	elif u < 0.4:
		lateral = first_support
		contact_roles.right = "SWING"
	elif u < 0.6:
		lateral = lerpf(first_support, second_support, jerk((u - 0.4) / 0.2))
	elif u < 0.8:
		lateral = second_support
		contact_roles.left = "SWING"
	else:
		lateral = second_support * (1.0 - jerk((u - 0.8) / 0.2))
	# All chains share this phase coordinate. Translation remains skeleton-only.
	var shift := Vector3(lateral, -0.02 * pow(sin(PI * u), 2), 0.0)
	for i in poses.size():
		poses[i].origin += shift
	var targets: Dictionary = {}
	var toe_targets: Dictionary = {}
	var extra_drop := 0.0
	for side in ["left", "right"]:
		var foot := named_index("Foot_L" if side == "left" else "Foot_R")
		var from := 0.6 if side == "left" else 0.2
		var to := 0.8 if side == "left" else 0.4
		var t := clampf((u - from) / (to - from), 0.0, 1.0)
		var target := Transform3D(Basis(a[foot].basis.get_rotation_quaternion().slerp(b[foot].basis.get_rotation_quaternion(), jerk(t))), a[foot].origin.lerp(b[foot].origin, jerk(t)))
		target.origin.y += 0.025 * pow(sin(PI * t), 2)
		var toe := named_index("Toes_L" if side == "left" else "Toes_R")
		var toe_local := (a[foot].affine_inverse() * a[toe]).interpolate_with(b[foot].affine_inverse() * b[toe], jerk(t))
		targets[side] = target
		toe_targets[side] = target * toe_local
		var thigh := int(data.conversions[side + "_thigh"].bone)
		var shin := int(data.conversions[side + "_shin"].bone)
		var reach := ready[thigh].origin.distance_to(ready[shin].origin) + ready[shin].origin.distance_to(ready[foot].origin) - 0.000001
		var horizontal := Vector2(poses[thigh].origin.x - target.origin.x, poses[thigh].origin.z - target.origin.z).length_squared()
		var allowed_height := sqrt(maxf(0.0, reach * reach - horizontal))
		extra_drop = maxf(extra_drop, poses[thigh].origin.y - target.origin.y - allowed_height)
	# Reach is solved through the shared pelvis height, never by stretching a leg.
	for i in poses.size():
		poses[i].origin.y -= extra_drop
	for side in ["left", "right"]:
		var target: Transform3D = targets[side]
		var toe_target: Transform3D = toe_targets[side]
		solve_step_leg(poses, side, target, toe_target.basis.y.normalized())
		move_joint(poses, int(data.conversions[side + "_toes"].bone), toe_target)
	# Upper carriage shares the support phase, reducing required ankle inversion.
	# Its measured trunk tilt must still remain inside the existing 10-degree gate.
	var carriage := 7.8 if phase == &"ENTRY" else 2.5
	var lean := carriage * jerk(u / 0.2) if u < 0.2 else carriage
	if u >= 0.4:
		lean *= 1.0 - jerk((u - 0.4) / 0.2)
	for key in ["spine_lower", "spine_mid", "chest"]:
		var index := int(data.conversions[key].bone)
		var target := poses[index]
		target.basis = (Basis(Vector3.BACK, deg_to_rad(-lean / 3.0)) * target.basis).orthonormalized()
		move_joint(poses, index, target)
	return poses

func named_index(name: String) -> int:
	for i in data.bones.size():
		if data.bones[i].blender_name == name:
			return i
	return -1

func move_joint(poses: Array[Transform3D], index: int, desired: Transform3D) -> void:
	var adjustment := desired * poses[index].affine_inverse()
	poses[index] = desired
	for i in range(index + 1, poses.size()):
		var parent := int(data.bones[i].parent)
		while parent >= 0:
			if parent == index:
				poses[i] = adjustment * poses[i]
				break
			parent = int(data.bones[parent].parent)

func solve_step_leg(poses: Array[Transform3D], side: String, foot_target: Transform3D, heading: Vector3) -> void:
	var thigh := int(data.conversions[side + "_thigh"].bone)
	var shin := int(data.conversions[side + "_shin"].bone)
	var foot := int(data.conversions[side + "_foot"].bone)
	var hip := poses[thigh].origin
	var upper := ready[thigh].origin.distance_to(ready[shin].origin)
	var lower := ready[shin].origin.distance_to(ready[foot].origin)
	var ray := foot_target.origin - hip
	var distance := clampf(ray.length(), absf(upper - lower) + 0.00001, upper + lower - 0.000001)
	var direction := ray.normalized()
	var pole_heading := heading
	var pole := (pole_heading - direction * pole_heading.dot(direction)).normalized()
	var cosine := clampf((upper * upper + distance * distance - lower * lower) / (2.0 * upper * distance), -1.0, 1.0)
	var knee := hip + direction * upper * cosine + pole * upper * sqrt(1.0 - cosine * cosine)
	# Source-bound heading distribution; foot target remains fixed. Select the
	# nearest leg heading that respects the existing ankle preferred envelope
	# and measured knee/toe tracking. Independent foot yaw is never introduced.
	var best_heading := heading
	var best_knee := knee
	var best_cost := INF
	var f: Dictionary = data.conversions[side + "_foot"]
	var sk: Dictionary = data.conversions[side + "_shin"]
	var rest_parent := matrix(data.canonical[side + "_shin"].canonical_rest_contract.basis_armature_local)
	var rest_child := matrix(data.canonical[side + "_foot"].canonical_rest_contract.basis_armature_local)
	var foot_canonical := matrix(f.left) * foot_target.basis * matrix(f.right)
	var sign_side := 1.0 if side == "left" else -1.0
	for sample in range(-40, 41):
		var angle := float(sample) * 0.25
		var candidate := Basis(Vector3.UP, deg_to_rad(angle)) * heading
		var candidate_pole := (candidate - direction * candidate.dot(direction)).normalized()
		var candidate_knee := hip + direction * upper * cosine + candidate_pole * upper * sqrt(1.0 - cosine * cosine)
		var basis := segment_basis(side + "_shin", (foot_target.origin - candidate_knee).normalized(), candidate)
		var shin_canonical := matrix(sk.left) * basis * matrix(sk.right)
		var delta := (rest_parent.transposed() * rest_child).transposed() * shin_canonical.transposed() * foot_canonical
		var inversion := rad_to_deg(asin(clampf(delta.z.x, -1.0, 1.0))) / sign_side
		var plantar := -rad_to_deg(asin(clampf(delta.y.z, -1.0, 1.0))) - (32.377 if side == "left" else 32.392)
		var knee_heading := Vector2(shin_canonical.z.x, -shin_canonical.z.y).normalized()
		var toe_heading := Vector2(heading.x, heading.z).normalized()
		var tracking := rad_to_deg(acos(clampf(knee_heading.dot(toe_heading), -1.0, 1.0)))
		var violation := maxf(0.0, -14.8 - inversion) + maxf(0.0, inversion - 24.8) + maxf(0.0, -19.8 - plantar) + maxf(0.0, plantar - 49.8) + maxf(0.0, tracking - 5.8)
		var cost := violation * 1000.0 + absf(angle)
		if cost < best_cost:
			best_cost = cost
			best_heading = candidate
			best_knee = candidate_knee
	var thigh_basis := segment_basis(side + "_thigh", (best_knee - hip).normalized(), best_heading)
	var shin_basis := segment_basis(side + "_shin", (foot_target.origin - best_knee).normalized(), best_heading)
	var th: Dictionary = data.conversions[side + "_thigh"]
	var thigh_canonical := matrix(th.left) * thigh_basis * matrix(th.right)
	var shin_canonical := matrix(sk.left) * shin_basis * matrix(sk.right)
	var rest_thigh := matrix(data.canonical[side + "_thigh"].canonical_rest_contract.basis_armature_local)
	var knee_delta := (rest_thigh.transposed() * rest_parent).transposed() * thigh_canonical.transposed() * shin_canonical
	var external := -rad_to_deg(atan2(knee_delta.z.x, knee_delta.x.x)) / sign_side
	# Avoid the serialized source bind's near-zero sign noise at the hinge floor.
	thigh_canonical *= Basis(Vector3.UP, deg_to_rad(sign_side * (0.05 - external)))
	thigh_basis = (matrix(th.left).inverse() * thigh_canonical * matrix(th.right).inverse()).orthonormalized()
	move_joint(poses, thigh, Transform3D(thigh_basis, hip))
	move_joint(poses, shin, Transform3D(shin_basis, best_knee))
	move_joint(poses, foot, foot_target)

func segment_basis(key: String, length_direction: Vector3, heading: Vector3) -> Basis:
	var c := Basis(Vector3(1,0,0), Vector3(0,0,-1), Vector3(0,1,0))
	var y := (c.inverse() * length_direction).normalized()
	var z0 := c.inverse() * heading
	var z := (z0 - y * z0.dot(y)).normalized()
	var x := y.cross(z).normalized()
	var canonical := Basis(x, y, z).orthonormalized()
	var r: Dictionary = data.conversions[key]
	return (matrix(r.left).inverse() * canonical * matrix(r.right).inverse()).orthonormalized()




