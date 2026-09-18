shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec4 top_color : source_color = vec4(0.78, 0.69, 0.55, 1.0);
uniform vec4 side_color : source_color = vec4(0.20, 0.025, 0.055, 1.0);
uniform vec4 trim_color : source_color = vec4(0.58, 0.38, 0.13, 1.0);
uniform float trim_start = 0.15;
uniform float upper_trim_strength = 1.0;
uniform float panel_spacing = 1.5;
uniform float seam_width = 0.026;
uniform float seam_strength = 0.36;
uniform float side_seam_strength = 0.48;

varying vec3 object_position;
varying vec3 object_normal;

void vertex() {
	object_position = VERTEX;
	object_normal = NORMAL;
}

void fragment() {
	float top_mask = smoothstep(0.65, 0.90, object_normal.y);
	float upper_edge = (1.0 - top_mask) * smoothstep(trim_start, 0.23, object_position.y);
	float panel_phase = fract(object_position.x / panel_spacing);
	float seam_distance = min(panel_phase, 1.0 - panel_phase);
	float seam_antialias = max(fwidth(object_position.x / panel_spacing), 0.001);
	float seam_mask = 1.0 - smoothstep(seam_width, seam_width + seam_antialias, seam_distance);
	vec3 seam_color = mix(top_color.rgb, trim_color.rgb, seam_strength);
	vec3 top_surface = mix(top_color.rgb, seam_color, seam_mask);
	vec3 palace_color = mix(side_color.rgb, top_surface, top_mask);
	vec3 trimmed_surface = mix(
		palace_color,
		trim_color.rgb,
		upper_edge * upper_trim_strength
	);
	float upper_side_band = (1.0 - top_mask)
		* smoothstep(0.13, 0.16, object_position.y)
		* (1.0 - smoothstep(0.205, 0.23, object_position.y));
	vec3 side_seam_color = mix(trim_color.rgb, side_color.rgb, 0.32);
	ALBEDO = mix(
		trimmed_surface,
		side_seam_color,
		seam_mask * upper_side_band * side_seam_strength
	);
	ROUGHNESS = mix(0.72, 0.38, top_mask);
	METALLIC = 0.0;
}
