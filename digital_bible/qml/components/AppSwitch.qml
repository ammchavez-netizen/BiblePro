import QtQuick
import QtQuick.Controls.Basic

Switch {
    id: control
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    opacity: enabled ? 1 : 0.5
    indicator: Rectangle {
        implicitWidth: 36
        implicitHeight: 20
        x: control.leftPadding
        y: parent.height / 2 - height / 2
        radius: 10
        color: control.checked ? Theme.accent : "#CBD5E1"
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle {
            x: control.checked ? parent.width - width - 2 : 2
            y: 2
            width: 16; height: 16; radius: 8
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
