"""Qt Quick / QML user interface for BibleQ-AI.

The QML files (qml/) only draw the interface. All behaviour lives in Python:
  controller.py     verse entry, versions, search, history, appearance, display
  ai_controller.py  AI Mode (chat, index management, models, API keys)
  preview_item.py   live preview that reuses canvas.Renderer (same look as the display)
  chat_model.py     the AI Mode conversation as a list model
"""
