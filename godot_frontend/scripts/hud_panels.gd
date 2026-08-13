# hud_panels.gd — Holographic Panels Controller (Godot 4)
extends Control

# System nodes
@onready var cpu_bar = $SystemPanel/VBox/CPU_Row/ProgressBar
@onready var cpu_val = $SystemPanel/VBox/CPU_Row/ValLabel
@onready var gpu_bar = $SystemPanel/VBox/GPU_Row/ProgressBar
@onready var gpu_val = $SystemPanel/VBox/GPU_Row/ValLabel
@onready var vram_val = $SystemPanel/VBox/VRAM_Row/ValLabel
@onready var ram_val = $SystemPanel/VBox/RAM_Row/ValLabel

# Perception nodes
@onready var cam_status_lbl = $PerceptionPanel/VBox/CamStatus
@onready var person_count_lbl = $PerceptionPanel/VBox/PersonCount
@onready var face_name_lbl = $PerceptionPanel/VBox/FaceCard/NameLabel
@onready var face_conf_lbl = $PerceptionPanel/VBox/FaceCard/ConfLabel

# Thought Pipeline & Subtitles
@onready var action_desc_lbl = $ActionPipeline/ActionDesc
@onready var subtitle_lbl = $SubtitleBanner/TextLabel
@onready var prompt_input = $BottomBar/PromptInput

func _ready() -> void:
	if SonIPC:
		SonIPC.telemetry_updated.connect(_on_telemetry_updated)
		SonIPC.perception_updated.connect(_on_perception_updated)
		SonIPC.thought_pipeline_updated.connect(_on_thought_pipeline)
		SonIPC.subtitle_received.connect(_on_subtitle_received)

	if prompt_input:
		prompt_input.text_submitted.connect(_on_prompt_submitted)

func _on_telemetry_updated(cpu: float, gpu: float, vram_gb: float, vram_total: float, ram_gb: float, ram_total: float) -> void:
	if cpu_bar and cpu_val:
		cpu_bar.value = cpu
		cpu_val.text = str(snapped(cpu, 0.1)) + "%"
	if gpu_bar and gpu_val:
		gpu_bar.value = gpu
		gpu_val.text = str(snapped(gpu, 0.1)) + "%"
	if vram_val:
		vram_val.text = str(snapped(vram_gb, 0.1)) + "/" + str(snapped(vram_total, 1.0)) + " GB"
	if ram_val:
		ram_val.text = str(snapped(ram_gb, 0.1)) + "/" + str(snapped(ram_total, 1.0)) + " GB"

func _on_perception_updated(camera_active: bool, person_count: int, face_name: String, confidence: float) -> void:
	if cam_status_lbl:
		cam_status_lbl.text = "CAMERA: ONLINE" if camera_active else "CAMERA: STANDBY"
		cam_status_lbl.modulate = Color(0.0, 1.0, 0.67) if camera_active else Color(1.0, 0.3, 0.3)
	if person_count_lbl:
		person_count_lbl.text = "OCCUPANCY: " + str(person_count) + " PERSON(S)"
	if face_name_lbl:
		face_name_lbl.text = "ID: " + face_name
	if face_conf_lbl:
		face_conf_lbl.text = "CONFIDENCE: " + str(int(confidence * 100)) + "%" if confidence > 0.0 else "SCANNING..."

func _on_thought_pipeline(_stage: int, _step_name: String, description: String) -> void:
	if action_desc_lbl:
		action_desc_lbl.text = "▶ " + description

func _on_subtitle_received(speaker: String, text: String) -> void:
	if subtitle_lbl:
		subtitle_lbl.text = "[" + speaker.to_upper() + "]: " + text

func _on_prompt_submitted(text: String) -> void:
	if text.strip() != "":
		SonIPC.send_user_prompt(text.strip())
		if prompt_input:
			prompt_input.text = ""

func _on_mic_button_pressed() -> void:
	SonIPC.send_voice_trigger()

func _on_camera_button_pressed() -> void:
	SonIPC.send_toggle_camera()
