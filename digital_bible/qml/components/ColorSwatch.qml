import QtQuick
import QtQuick.Controls.Basic

// Click to pick a color.
AbstractButton {
    id: control
    property color swatch: "white"
    hoverEnabled: true
    implicitWidth: 44
    implicitHeight: 26
    background: Rectangle {
        radius: 6
        color: control.swatch
        border.width: control.hovered ? 2 : 1
        border.color: control.hovered ? Theme.accent : Theme.borderStrong
    }
}
