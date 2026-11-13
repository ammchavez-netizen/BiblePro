import QtQuick
import QtQuick.Controls.Basic

// Small pill button, e.g. a favorite version.
AbstractButton {
    id: control
    property bool selected: false
    property string hint: ""
    hoverEnabled: true
    implicitHeight: Theme.s(28)
    implicitWidth: label.implicitWidth + Theme.s(24)
    ToolTip.visible: hint !== "" && hovered
    ToolTip.text: hint
    ToolTip.delay: 500
    contentItem: Text {
        id: label
        text: control.text
        font.family: Theme.font
        font.pixelSize: Theme.s(12)
        font.weight: Font.DemiBold
        color: control.selected ? Theme.accentText : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: height / 2
        color: control.selected ? Theme.accent : control.hovered ? "#F2F6FE" : Theme.surface
        border.width: control.selected ? 0 : 1
        border.color: Theme.border
        Rectangle {
            z: -1
            anchors.fill: parent; anchors.topMargin: Theme.s(2); anchors.bottomMargin: -2
            radius: parent.radius
            color: control.selected ? Qt.rgba(20/255, 99/255, 243/255, 0.22) : Qt.rgba(17/255, 26/255, 51/255, 0.05)
        }
    }
}
