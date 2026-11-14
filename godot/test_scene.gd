# test_scene.gd — Offline Interactive Visual Testbed for SON Mini Assistant
extends Control

const SonStateController = preload("res://son_state_controller.gd")

@onready var mini_win: Control = $MiniWindow
@onready var amplitude_slider: HSlider = $TestDashboard/VBox/AmpSlider
@onready var sim_chat_btn: Button = $TestDashboard/VBox/SimChatBtn

func _ready() -> void:
    print("[TestScene] Initialized offline test harness.")

func _on_idle_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.IDLE)

func _on_listening_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.LISTENING)

func _on_thinking_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.THINKING)

func _on_speaking_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.SPEAKING)

func _on_executing_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.EXECUTING)
    mini_win._show_activity_banner("Executing: create_office_document (leave_letter.docx)", true)

func _on_vision_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.VISION)
    mini_win._show_activity_banner("Vision: Analyzing desktop workspace...", true)

func _on_warning_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.WARNING)
    mini_win._on_ws_approval_requested({
        "request_id": "test_appr_1",
        "tool_name": "delete_directory",
        "reason": "Destructive file action requested"
    })

func _on_error_pressed() -> void:
    mini_win.state_controller.set_state(SonStateController.State.ERROR)
    mini_win._append_chat_message("system", "Error: Simulated connection failure or command exception.")

func _on_amp_slider_value_changed(value: float) -> void:
    mini_win.state_controller.set_audio_amplitude(value)

func _on_toggle_mode_pressed() -> void:
    mini_win._toggle_mode()

func _on_sim_chat_pressed() -> void:
    mini_win._append_chat_message("user", "Hello SON, what's my system status?")
    mini_win.state_controller.set_state(SonStateController.State.THINKING)
    
    get_tree().create_timer(1.2).timeout.connect(func():
        mini_win.state_controller.set_state(SonStateController.State.SPEAKING)
        mini_win._append_chat_message("assistant", "Your Ryzen 7 7840HS CPU is at 14% and RTX 4060 GPU is running smooth at 42°C with 2.1 GB VRAM utilized.")
        get_tree().create_timer(2.5).timeout.connect(func():
            mini_win.state_controller.set_state(SonStateController.State.IDLE)
        )
    )
