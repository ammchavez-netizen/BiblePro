import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: control
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    implicitHeight: Theme.controlHeight
    opacity: enabled ? 1 : 0.5
    background: Rectangle {
        radius: Theme.radiusSmall
        color: Theme.surface
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.borderStrong
    }
    contentItem: Text {
        leftPadding: 12
        rightPadding: control.indicator.width + 6
        text: control.displayText
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    popup.background: Rectangle {
        radius: Theme.radiusSmall
        color: Theme.surface
        border.color: Theme.border
    }
}
