shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec4 top_color : source_color = vec4(0.78, 0.69, 0.55, 1.0);
uniform vec4 side_color : source_color = vec4(0.20, 0.025, 0.055, 1.0);
uniform vec4 trim_color : source_color = vec4(0.58, 0.38, 0.13, 1.0);
uniform float trim_start = 0.15;

varying vec3 object_position;
varying vec3 object_normal;

void vertex() {
	object_position = VERTEX;
	object_normal = NORMAL;
}

void fragment() {
	float top_mask = smoothstep(0.65, 0.90, object_normal.y);
	float upper_edge = (1.0 - top_mask) * smoothstep(trim_start, 0.23, object_position.y);
	vec3 palace_color = mix(side_color.rgb, top_color.rgb, top_mask);
	ALBEDO = mix(palace_color, trim_color.rgb, upper_edge);
	ROUGHNESS = mix(0.72, 0.38, top_mask);
	METALLIC = 0.0;
}
