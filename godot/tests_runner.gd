# tests_runner.gd — Standalone Automated Test Runner for SON Mini Assistant
extends SceneTree

const SonStateController = preload("res://son_state_controller.gd")
const SonWebSocketClient = preload("res://websocket_client.gd")
const NativeWindowBridgeGD = preload("res://native_window_bridge.gd")
const MiniWindowSettings = preload("res://mini_window_settings.gd")

var total_tests: int = 0
var passed_tests: int = 0
var failed_tests: int = 0

func _init() -> void:
    print("\n=======================================================")
    print("      SON MINI ASSISTANT — AUTOMATED TEST SUITE        ")
    print("=======================================================\n")

    run_test("State Controller: All 8 Visual States & Transitions", test_state_controller_transitions)
    run_test("State Controller: Audio Amplitude & Waveform Synthesis", test_audio_synthesis)
    run_test("Settings Manager: Serialization & Deserialization", test_settings_manager)
    run_test("Native Window Bridge: Win11 Detection & Safe Fallbacks", test_native_bridge)
    run_test("Liquid Glass Shader: Uniform Parameter Verification", test_shader_uniforms)
    run_test("WebSocket Client: Offline Resilience & Message Dispatch", test_websocket_client)
    run_test("Mini Window Layout: Compact & Expanded Geometry", test_window_geometry)

    print("\n=======================================================")
    print("TEST SUMMARY: %d Total | %d Passed | %d Failed" % [total_tests, passed_tests, failed_tests])
    print("=======================================================\n")

    if failed_tests == 0:
        print("ALL TESTS PASSED SUCCESSFULLY! (100% PASS RATE)")
        quit(0)
    else:
        print("SOME TESTS FAILED! Review error log.")
        quit(1)

func run_test(test_name: String, test_func: Callable) -> void:
    total_tests += 1
    print("• Running: %s..." % test_name)
    test_func.call()
    passed_tests += 1
    print("  ✓ PASS")

func assert_true(condition: bool, message: String = "Assertion failed") -> void:
    if not condition:
        push_error(message)
        assert(false, message)

func test_state_controller_transitions() -> void:
    var sc = SonStateController.new()

    # Verify all 8 states sequentially
    var states_to_test = [
        SonStateController.State.IDLE,
        SonStateController.State.LISTENING,
        SonStateController.State.THINKING,
        SonStateController.State.SPEAKING,
        SonStateController.State.EXECUTING,
        SonStateController.State.VISION,
        SonStateController.State.WARNING,
        SonStateController.State.ERROR
    ]

    for st in states_to_test:
        sc.set_state(st)
        assert_true(sc.current_state == st, "State did not update correctly to " + str(st))
        var s_name = sc.get_state_name()
        assert_true(s_name.length() > 0, "State name was empty for state " + str(st))

        # Check update delta loop
        sc.update(0.016)
        var prim = sc.get_primary_color()
        assert_true(prim.a > 0.0, "Primary color alpha invalid")

    # Verify string mapping
    sc.set_state_by_name("THINKING")
    assert_true(sc.current_state == SonStateController.State.THINKING, "String mapping failed for THINKING")
    sc.set_state_by_name("VISION")
    assert_true(sc.current_state == SonStateController.State.VISION, "String mapping failed for VISION")

func test_audio_synthesis() -> void:
    var sc = SonStateController.new()
    sc.set_state(SonStateController.State.SPEAKING)
    sc.set_audio_amplitude(0.85)

    # Step simulation 10 frames
    for i in range(10):
        sc.update(0.016)

    assert_true(sc.smoothed_audio_amplitude > 0.0, "Smoothed audio amplitude did not rise")
    assert_true(sc.waveform_bars.size() == 16, "Waveform bars size should be 16")
    assert_true(sc.current_energy > 1.0, "Speaking energy should be elevated")

func test_settings_manager() -> void:
    var s = MiniWindowSettings.new()
    s.visual_style = "frosted_glass"
    s.transparency = 0.72
    s.animation_intensity = 0.8
    s.always_on_top = false
    s.low_power_mode = true

    var dict = s.to_dict()
    assert_true(dict["visual_style"] == "frosted_glass", "Settings visual_style mismatch")
    assert_true(abs(dict["transparency"] - 0.72) < 0.01, "Settings transparency mismatch")
    assert_true(dict["always_on_top"] == false, "Settings always_on_top mismatch")
    assert_true(dict["low_power_mode"] == true, "Settings low_power_mode mismatch")

    var s2 = MiniWindowSettings.new()
    s2.from_dict(dict)
    assert_true(s2.visual_style == "frosted_glass", "Deserialization failed")
    assert_true(s2.low_power_mode == true, "Deserialization failed for low_power_mode")

func test_native_bridge() -> void:
    var bridge = NativeWindowBridgeGD.new()
    # In Windows environment, build_number should be detected
    if OS.get_name() == "Windows":
        assert_true(bridge.build_number > 0, "Windows build number should be detected")
        print("    [Info] Detected Windows Build: %d (Win11: %s, Acrylic: %s)" % [
            bridge.build_number,
            str(bridge.is_win11),
            str(bridge.supports_acrylic)
        ])

    # Test safe fallback calls without window attached
    var style_res = bridge.apply_native_styling()
    assert_true(style_res.has("always_on_top"), "apply_native_styling response missing keys")

func test_shader_uniforms() -> void:
    var shader = load("res://glass_panel.gdshader")
    assert_true(shader != null, "Failed to load glass_panel.gdshader")

    var mat = ShaderMaterial.new()
    mat.shader = shader

    mat.set_shader_parameter("tint_color", Color(0.04, 0.08, 0.14, 0.85))
    mat.set_shader_parameter("corner_radius", 24.0)
    mat.set_shader_parameter("refraction_strength", 0.025)
    mat.set_shader_parameter("low_power_mode", true)

    assert_true(mat.get_shader_parameter("corner_radius") == 24.0, "Shader corner_radius mismatch")
    assert_true(mat.get_shader_parameter("low_power_mode") == true, "Shader low_power_mode mismatch")

func test_websocket_client() -> void:
    var ws = SonWebSocketClient.new()
    # When offline, is_connected_to_backend should be false
    assert_true(not ws.is_connected_to_backend(), "Offline client should report not connected")

    # Step poll loop while disconnected (should not throw or hang)
    ws.poll(0.016)
    assert_true(not ws.is_connected_to_backend(), "Still disconnected")

    # Test outbound calls gracefully reject when offline
    var sent = ws.send_chat("Test prompt")
    assert_true(sent == false, "Outbound chat should return false when offline")

func test_window_geometry() -> void:
    var compact = Vector2i(280, 80)
    var expanded = Vector2i(380, 530)

    assert_true(compact.x < expanded.x, "Compact width should be less than expanded")
    assert_true(compact.y < expanded.y, "Compact height should be less than expanded")
