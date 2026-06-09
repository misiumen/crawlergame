extends Control
## Screen-fixed UI painter. Lives on a CanvasLayer above the world camera and
## delegates all drawing to the controller's _draw_ui(c) — the controller keeps
## every piece of state; this node is a dumb canvas. mouse_filter is IGNORE so
## clicks fall through to the controller's _unhandled_input (which hit-tests the
## click zones the UI pass registers).

var controller: Node2D = null

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)

func _draw() -> void:
	if controller != null:
		controller._draw_ui(self)
