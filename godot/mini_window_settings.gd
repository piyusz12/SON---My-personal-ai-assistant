# mini_window_settings.gd — Persistent Configuration Manager for SON Mini Assistant
class_name MiniWindowSettings
extends RefCounted

signal settings_changed(settings: Dictionary)

const SETTINGS_FILE_PATH = "user://mini_assistant_settings.json"

var visual_style: String = "liquid_glass"     # "liquid_glass", "frosted_glass", "solid"
var transparency: float = 0.85                # 0.1 to 1.0
var animation_intensity: float = 1.0          # 0.0 to 1.0
var always_on_top: bool = true
var low_power_mode: bool = false
var startup_position: String = "bottom_right" # "bottom_right", "top_right", "center", "custom"
var custom_pos: Vector2i = Vector2i(100, 100)
var server_url: String = "ws://127.0.0.1:8765"
var auth_token: String = ""

func _init() -> void:
    load_settings()

func load_settings() -> void:
    if not FileAccess.file_exists(SETTINGS_FILE_PATH):
        # Save default settings
        save_settings()
        return

    var file = FileAccess.open(SETTINGS_FILE_PATH, FileAccess.READ)
    if not file:
        return

    var content = file.get_as_text()
    file.close()

    var parsed = JSON.parse_string(content)
    if typeof(parsed) == TYPE_DICTIONARY:
        from_dict(parsed)

func save_settings() -> bool:
    var file = FileAccess.open(SETTINGS_FILE_PATH, FileAccess.WRITE)
    if not file:
        return false

    var json_str = JSON.stringify(to_dict(), "  ")
    file.store_string(json_str)
    file.close()
    settings_changed.emit(to_dict())
    return true

func to_dict() -> Dictionary:
    return {
        "visual_style": visual_style,
        "transparency": transparency,
        "animation_intensity": animation_intensity,
        "always_on_top": always_on_top,
        "low_power_mode": low_power_mode,
        "startup_position": startup_position,
        "custom_pos_x": custom_pos.x,
        "custom_pos_y": custom_pos.y,
        "server_url": server_url,
        "auth_token": auth_token
    }

func from_dict(d: Dictionary) -> void:
    visual_style = str(d.get("visual_style", "liquid_glass"))
    transparency = clamp(float(d.get("transparency", 0.85)), 0.1, 1.0)
    animation_intensity = clamp(float(d.get("animation_intensity", 1.0)), 0.0, 1.0)
    always_on_top = bool(d.get("always_on_top", true))
    low_power_mode = bool(d.get("low_power_mode", false))
    startup_position = str(d.get("startup_position", "bottom_right"))
    custom_pos = Vector2i(
        int(d.get("custom_pos_x", 100)),
        int(d.get("custom_pos_y", 100))
    )
    server_url = str(d.get("server_url", "ws://127.0.0.1:8765"))
    auth_token = str(d.get("auth_token", ""))
