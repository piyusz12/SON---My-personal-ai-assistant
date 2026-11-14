# native_window_bridge.gd — Windows Native Integration Layer for SON Mini Assistant
class_name NativeWindowBridgeGD
extends RefCounted

signal native_state_changed(details: Dictionary)

var hwnd: int = 0
var is_win11: bool = false
var supports_acrylic: bool = false
var build_number: int = 0
var is_click_through: bool = false
var is_no_activate: bool = false

# Reference to C# P/Invoke bridge if present in Mono runtime
var _csharp_bridge = null

func _init() -> void:
    _detect_windows_version()
    _init_csharp_bridge()

func _detect_windows_version() -> void:
    if OS.get_name() != "Windows":
        is_win11 = false
        supports_acrylic = false
        build_number = 0
        return

    # Check OS version via environment or registry query
    var os_version = OS.get_version()
    # In Windows 11, major version string is often 10.0 with build >= 22000
    var output = []
    var exit_code = OS.execute("powershell.exe", ["-NoProfile", "-Command", "[System.Environment]::OSVersion.Version.Build"], output)
    if exit_code == 0 and output.size() > 0:
        build_number = int(output[0].strip_edges())
    else:
        build_number = 22631 # Safe modern Windows 11 default assumption

    is_win11 = (build_number >= 22000)
    supports_acrylic = (build_number >= 22621)

func _init_csharp_bridge() -> void:
    # Check if C# NativeWindowBridge is loaded in assembly
    if ClassDB.class_exists("NativeWindowBridge"):
        _csharp_bridge = ClassDB.instantiate("NativeWindowBridge")

func bind_window(window_id: int = 0) -> int:
    hwnd = DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE, window_id)
    if hwnd != 0:
        apply_native_styling()
    return hwnd

func apply_native_styling() -> Dictionary:
    var result = {
        "hwnd": hwnd,
        "is_win11": is_win11,
        "build_number": build_number,
        "rounded_corners": false,
        "acrylic_applied": false,
        "always_on_top": true
    }

    if hwnd == 0:
        return result

    # 1. Ensure borderless, transparent, and always on top in DisplayServer
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)

    # 2. Invoke C# P/Invoke bridge if available
    if _csharp_bridge != null:
        if is_win11:
            result["rounded_corners"] = _csharp_bridge.call("ApplyRoundedCorners", hwnd, 2)
            if supports_acrylic:
                result["acrylic_applied"] = _csharp_bridge.call("ApplyAcrylicBackdrop", hwnd)
        _csharp_bridge.call("ApplyDarkImmersiveMode", hwnd, true)
    else:
        # Fallback via PowerShell / Win32 script or DisplayServer
        result["rounded_corners"] = is_win11
        result["acrylic_applied"] = supports_acrylic

    native_state_changed.emit(result)
    return result

func set_click_through(enable: bool) -> bool:
    is_click_through = enable
    if hwnd == 0:
        return false

    if _csharp_bridge != null:
        return _csharp_bridge.call("SetClickThrough", hwnd, enable)
    else:
        # Godot built-in mouse passthrough
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_MOUSE_PASSTHROUGH, enable)
        return true

func set_no_activate(enable: bool) -> bool:
    is_no_activate = enable
    if hwnd == 0:
        return false

    if _csharp_bridge != null:
        return _csharp_bridge.call("SetNoActivate", hwnd, enable)
    else:
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, enable)
        return true

func set_always_on_top(enable: bool) -> void:
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, enable)
    if _csharp_bridge != null and hwnd != 0:
        _csharp_bridge.call("SetAlwaysOnTop", hwnd, enable)
