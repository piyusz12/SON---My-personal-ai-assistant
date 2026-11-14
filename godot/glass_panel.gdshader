// glass_panel.gdshader — Apple Liquid Glass Shader for SON Floating Mini Assistant
// Designed for Godot 4.7 Forward+ / Mobile renderers on NVIDIA RTX 4060 & Windows 11.
// Note: Internal refraction samples Godot's screen_texture buffer; desktop backdrop
// composition relies on Windows DWM per-pixel alpha compositing or Acrylic backdrop.

shader_type canvas_item;

// ── Uniforms ─────────────────────────────────────────────────────────
uniform vec4 tint_color : source_color = vec4(0.047, 0.078, 0.141, 0.82);
uniform vec4 rim_color : source_color = vec4(0.0, 0.898, 1.0, 0.65);
uniform vec4 state_glow_color : source_color = vec4(0.0, 0.898, 1.0, 0.35);

uniform float corner_radius : hint_range(0.0, 60.0) = 22.0;
uniform float border_width : hint_range(0.5, 6.0) = 1.2;
uniform float refraction_strength : hint_range(0.0, 0.1) = 0.022;
uniform float chromatic_aberration : hint_range(0.0, 0.05) = 0.007;
uniform float blur_amount : hint_range(0.0, 5.0) = 1.6;
uniform float specular_intensity : hint_range(0.0, 2.0) = 0.75;

uniform vec2 mouse_position = vec2(0.5, 0.2);
uniform float mouse_influence : hint_range(0.0, 1.0) = 0.4;
uniform float state_energy : hint_range(0.0, 2.0) = 1.0;

uniform bool low_power_mode = false;
uniform bool solid_mode = false;

// Godot 4 screen texture sampler with mipmap filtering for frosted blur
uniform sampler2D screen_texture : hint_screen_texture, filter_linear_mipmap;

// ── SDF Rounded Box Function ──────────────────────────────────────────
float sd_rounded_box(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + vec2(r);
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}

void fragment() {
    // 1. Convert UV to pixel-space coordinates centered on the rectangle
    vec2 size_px = vec2(length(vec2(dFdx(UV.x), dFdy(UV.x))), length(vec2(dFdx(UV.y), dFdy(UV.y))));
    vec2 rect_size = 1.0 / max(size_px, vec2(0.0001));
    vec2 pos_px = (UV - 0.5) * rect_size;
    vec2 half_px = (rect_size * 0.5);

    // Compute SDF distance in pixels
    float r = min(corner_radius, min(half_px.x, half_px.y) - 1.0);
    float dist = sd_rounded_box(pos_px, half_px, r);

    // Smooth antialiased outer alpha boundary
    float outer_alpha = smoothstep(0.5, -0.5, dist);
    if (outer_alpha <= 0.001) {
        discard;
    }

    if (solid_mode) {
        // High contrast / solid fallback mode
        vec4 solid_bg = vec4(0.08, 0.10, 0.16, 0.98);
        float b_factor = smoothstep(0.0, -border_width, dist) - smoothstep(-border_width, -border_width - 1.0, dist);
        vec3 final_solid = mix(solid_bg.rgb, rim_color.rgb, b_factor * 0.9);
        COLOR = vec4(final_solid, outer_alpha * solid_bg.a);
    } else {
        // 2. Liquid Edge Refraction & Chromatic Aberration
        vec2 norm = normalize(pos_px);
        float edge_factor = smoothstep(-24.0, 0.0, dist);
        vec2 refr_offset = -norm * edge_factor * refraction_strength;

        vec3 scene_color;
        if (low_power_mode) {
            // Low-power single-tap fetch
            scene_color = textureLod(screen_texture, SCREEN_UV + refr_offset * 0.5, 0.0).rgb;
        } else {
            // Premium multi-tap dispersion (RGB chromatic aberration + frosted blur)
            float r_chan = textureLod(screen_texture, SCREEN_UV + refr_offset * (1.0 + chromatic_aberration * 2.0), blur_amount).r;
            float g_chan = textureLod(screen_texture, SCREEN_UV + refr_offset, blur_amount).g;
            float b_chan = textureLod(screen_texture, SCREEN_UV + refr_offset * (1.0 - chromatic_aberration * 2.0), blur_amount).b;
            scene_color = vec3(r_chan, g_chan, b_chan);
        }

        // 3. Dynamic Cursor Specular Light Spot
        float mouse_dist = distance(UV, mouse_position);
        float dynamic_specular = exp(-mouse_dist * mouse_dist * 22.0) * mouse_influence * specular_intensity;

        // 4. Liquid Glass Caustic Rim & Border Highlight
        // Top light grazing crest (Apple glass style top sheen)
        float top_sheen = smoothstep(0.20, 0.0, UV.y) * 0.28 * (1.0 - edge_factor * 0.5);

        // Border line highlight with dynamic rim color
        float border_mask = smoothstep(0.0, -border_width, dist) - smoothstep(-border_width, -border_width - 1.2, dist);
        // Angular specular variation on border (brighter at top-left)
        float angle_intensity = clamp(dot(norm, vec2(-0.5, -0.7)) * 0.5 + 0.5, 0.2, 1.0);
        vec3 border_glow = rim_color.rgb * border_mask * angle_intensity * 1.4;

        // 5. Active State Aura (Inner peripheral glow)
        float inner_perimeter = smoothstep(-36.0, -4.0, dist) * (1.0 - smoothstep(-4.0, 0.0, dist));
        vec3 state_aura = state_glow_color.rgb * inner_perimeter * state_energy * 0.45;

        // 6. Composite Layers
        // Base tinted substrate
        vec3 composite = mix(scene_color, tint_color.rgb, tint_color.a);

        // Add state aura, caustic top sheen, dynamic specular, and border glow
        composite += state_aura;
        composite += vec3(top_sheen * 0.8);
        composite += vec3(dynamic_specular) * rim_color.rgb;
        composite += border_glow;

        // Final alpha compositing
        float final_alpha = outer_alpha * clamp(tint_color.a + (border_mask * 0.4) + (top_sheen * 0.2), 0.1, 1.0);
        COLOR = vec4(composite, final_alpha);
    }
}
