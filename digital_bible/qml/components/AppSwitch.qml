import QtQuick
import QtQuick.Controls.Basic

Switch {
    id: control
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    opacity: enabled ? 1 : 0.5
    indicator: Rectangle {
        implicitWidth: Theme.s(44)
        implicitHeight: Theme.s(24)
        x: control.leftPadding
        y: parent.height / 2 - height / 2
        radius: Theme.s(12)
        color: control.checked ? Theme.accent : "#CBD5E1"
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle {
            x: control.checked ? parent.width - width - 2 : 2
            y: 2
            width: Theme.s(20); height: Theme.s(20); radius: Theme.s(10)
            color: "white"
            Behavior on x { NumberAnimation { duration: 120 } }
        }
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        leftPadding: control.indicator.width + 8
    }
}
