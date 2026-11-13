import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: control
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    implicitHeight: Theme.controlHeight
    opacity: enabled ? 1 : 0.5
    leftPadding: Theme.s(12)
    rightPadding: Theme.s(32)
    indicator: Icon {
        x: control.width - width - Theme.s(11)
        y: (control.height - height) / 2
        name: "chevron-down"; size: Theme.s(14); strokeWidth: 2.4; color: Theme.textMuted
    }
    background: Rectangle {
        radius: Theme.radiusSmall
        color: Theme.surface
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.borderStrong
    }
    contentItem: Text {
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
