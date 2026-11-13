import QtQuick
import QtQuick.Controls.Basic

// Button with variants: "primary", "secondary" (default), "soft" (light blue), "ghost", "danger".
Button {
    id: control
    property string variant: "secondary"
    property bool compact: false
    property string iconName: ""          // optional line icon before the text
    property bool alignLeft: false         // icon + text at the left instead of centered
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    font.weight: variant === "primary" ? Font.DemiBold : Font.Medium
    implicitHeight: compact ? 32 : Theme.controlHeight
    leftPadding: compact ? 12 : 18
    rightPadding: compact ? 12 : 18
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    readonly property color _bg: {
        if (!enabled) return Theme.surfaceAlt
        if (variant === "primary") return down ? "#1E40AF" : hovered ? Theme.accentHover : Theme.accent
        if (variant === "danger") return down ? "#FEE2E2" : hovered ? Theme.dangerSoft : Theme.surface
        if (variant === "soft") return down ? "#D6E4FF" : hovered ? "#DDE8FF" : Theme.accentSoft
        if (variant === "ghost") return down ? "#DCE5F5" : hovered ? "#EAF0FB" : "transparent"
        if (checked) return Theme.accentSoft
        return down ? "#E9EFF9" : hovered ? "#F5F8FE" : Theme.surface
    }
    readonly property color _fg: !control.enabled ? Theme.textFaint
             : control.variant === "primary" ? Theme.accentText
             : control.variant === "danger" ? Theme.danger
             : control.variant === "soft" ? Theme.accent
             : control.checked ? Theme.accent : Theme.text
    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        Row {
            id: row
            x: control.alignLeft ? 0 : Math.round((parent.width - width) / 2)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.s(8)
            Icon {
                visible: control.iconName !== ""
                anchors.verticalCenter: parent.verticalCenter
                name: control.iconName
                size: Theme.s(control.compact ? 15 : 19)
                strokeWidth: 2.2
                color: control._fg
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: control.text
                font: control.font
                color: control._fg
            }
        }
    }
    background: Rectangle {
        radius: Theme.radiusSmall
        // soft drop shadow for raised buttons
        Rectangle {
            visible: control.variant !== "ghost" && control.enabled
            z: -1
            anchors.fill: parent; anchors.topMargin: Theme.s(2); anchors.bottomMargin: -2
            radius: parent.radius
            color: control.variant === "primary" ? Qt.rgba(20/255, 99/255, 243/255, 0.25) : Qt.rgba(17/255, 26/255, 51/255, 0.06)
        }
        color: control._bg
        border.width: control.variant === "ghost" || control.variant === "primary" ? 0 : 1
        border.color: control.checked ? Theme.accent
                    : control.visualFocus ? Theme.accent
                    : control.variant === "danger" ? "#FECACA"
                    : control.variant === "soft" ? Theme.accentBorder : Theme.border
        Behavior on color { ColorAnimation { duration: 90 } }
    }
}
