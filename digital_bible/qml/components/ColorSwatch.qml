import QtQuick
import QtQuick.Controls.Basic

// Click to pick a color.
AbstractButton {
    id: control
    property color swatch: "white"
    hoverEnabled: true
    implicitWidth: Theme.s(44)
    implicitHeight: Theme.s(26)
    background: Rectangle {
        radius: Theme.s(6)
        color: control.swatch
        border.width: control.hovered ? 2 : 1
        border.color: control.hovered ? Theme.accent : Theme.borderStrong
    }
}
