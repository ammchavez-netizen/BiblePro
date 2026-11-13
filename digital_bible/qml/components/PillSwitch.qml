import QtQuick
import QtQuick.Controls.Basic

// A switch inside a rounded white pill (display options row).
AppSwitch {
    id: control
    implicitHeight: Theme.s(40)
    leftPadding: Theme.s(10)
    rightPadding: Theme.s(16)
    background: Rectangle {
        radius: Theme.radiusSmall
        color: Theme.surface
        border.color: Theme.border
        Rectangle {
            z: -1
            anchors.fill: parent; anchors.topMargin: Theme.s(2); anchors.bottomMargin: -2
            radius: parent.radius; color: Qt.rgba(17/255, 26/255, 51/255, 0.06)
        }
    }
}
