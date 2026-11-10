"""Qt Quick / QML user interface for BiblePro.

The QML files (qml/) only draw the interface. All behaviour lives in Python:
  controller.py     verse entry, versions, search, history, appearance, display
  ai_controller.py  AI Mode (chat, index management, models, API keys)
  preview_item.py   live preview that reuses canvas.Renderer (same look as the display)

The previous Qt Widgets window (control_window.py) is kept as a fallback:
start with  --classic  to use it.
"""
