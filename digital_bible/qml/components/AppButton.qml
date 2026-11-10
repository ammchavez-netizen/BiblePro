import QtQuick
import QtQuick.Controls.Basic

// Button with variants: "primary", "secondary" (default), "ghost", "danger".
Button {
    id: control
    property string variant: "secondary"
    property bool compact: false
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    font.weight: variant === "primary" ? Font.DemiBold : Font.Medium
    implicitHeight: compact ? 30 : Theme.controlHeight
    leftPadding: compact ? 10 : 14
    rightPadding: compact ? 10 : 14
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    readonly property color _bg: {
        if (!enabled) return Theme.surfaceAlt
        if (variant === "primary") return down ? "#1E40AF" : hovered ? Theme.accentHover : Theme.accent
        if (variant === "danger") return down ? "#FEE2E2" : hovered ? Theme.dangerSoft : Theme.surface
        if (variant === "ghost") return down ? "#E2E8F0" : hovered ? "#F1F5F9" : "transparent"
        if (checked) return Theme.accentSoft
        return down ? "#EEF2F7" : hovered ? "#F8FAFC" : Theme.surface
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: !control.enabled ? Theme.textFaint
             : control.variant === "primary" ? Theme.accentText
             : control.variant === "danger" ? Theme.danger
             : control.checked ? Theme.accent : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Theme.radiusSmall
        color: control._bg
        border.width: control.variant === "ghost" || control.variant === "primary" ? 0 : 1
        border.color: control.checked ? Theme.accent
                    : control.visualFocus ? Theme.accent
                    : control.variant === "danger" ? "#FECACA" : Theme.border
        Behavior on color { ColorAnimation { duration: 90 } }
    }
}
