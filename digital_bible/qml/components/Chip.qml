import QtQuick
import QtQuick.Controls.Basic

// Small pill button, e.g. a favorite version.
AbstractButton {
    id: control
    property bool selected: false
    property string hint: ""
    hoverEnabled: true
    implicitHeight: 28
    implicitWidth: label.implicitWidth + 22
    ToolTip.visible: hint !== "" && hovered
    ToolTip.text: hint
    ToolTip.delay: 500
    contentItem: Text {
        id: label
        text: control.text
        font.family: Theme.font
        font.pixelSize: Theme.fontSmall
        font.weight: Font.DemiBold
        color: control.selected ? Theme.accentText : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: height / 2
        color: control.selected ? Theme.accent : control.hovered ? "#EEF2F7" : Theme.surfaceAlt
        border.width: control.selected ? 0 : 1
        border.color: Theme.border
    }
}
