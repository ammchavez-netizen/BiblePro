import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: control
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    color: Theme.text
    placeholderTextColor: Theme.textFaint
    selectByMouse: true
    selectionColor: "#BFDBFE"
    selectedTextColor: Theme.text
    implicitHeight: Theme.controlHeight
    leftPadding: Theme.s(12)
    rightPadding: Theme.s(12)
    background: Rectangle {
        radius: Theme.radiusSmall
        color: control.enabled ? Theme.surface : Theme.surfaceAlt
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.borderStrong
    }
}
