import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Sidebar entry: icon + label; filled blue when selected.
AbstractButton {
    id: control
    property string iconName: ""
    property bool selected: false
    property bool compact: false          // icon only (narrow windows)
    hoverEnabled: true
    implicitHeight: Theme.s(44)
    implicitWidth: Theme.s(compact ? 44 : 150)
    ToolTip.visible: compact && hovered
    ToolTip.text: text
    ToolTip.delay: 400
    background: Rectangle {
        radius: Theme.s(12)
        color: control.selected ? Theme.accent : control.hovered ? Qt.rgba(1, 1, 1, 0.6) : "transparent"
        gradient: control.selected ? selGrad : null
        Gradient {
            id: selGrad
            GradientStop { position: 0.0; color: "#3D8BFF" }
            GradientStop { position: 1.0; color: "#1463F3" }
        }
        Behavior on color { ColorAnimation { duration: 100 } }
        // soft glow under the selected entry
        Rectangle {
            visible: control.selected
            z: -1
            anchors.fill: parent; anchors.topMargin: Theme.s(4); anchors.bottomMargin: -4
            radius: Theme.s(12); color: Qt.rgba(20/255, 99/255, 243/255, 0.18)
        }
    }
    contentItem: RowLayout {
        spacing: Theme.s(12)
        Icon {
            Layout.leftMargin: Theme.s(control.compact ? 11 : 14)
            name: control.iconName
            size: Theme.s(21)
            color: control.selected ? "white" : control.iconName === "sparkle" ? "#2D6BF0" : Theme.navy
        }
        Text {
            visible: !control.compact
            Layout.fillWidth: true
            text: control.text
            font.family: Theme.font
            font.pixelSize: Theme.s(14)
            font.weight: control.selected ? Font.DemiBold : Font.Normal
            color: control.selected ? "white" : Theme.navy
            elide: Text.ElideRight
        }
    }
}
