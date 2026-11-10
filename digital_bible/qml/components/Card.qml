import QtQuick

// White rounded panel with a subtle border and soft shadow (works on any Qt 6).
Item {
    id: root
    default property alias content: inner.data
    property int padding: Theme.pad
    property alias color: bgRect.color
    implicitWidth: inner.childrenRect.width + padding * 2
    implicitHeight: inner.childrenRect.height + padding * 2

    // soft shadow: two faint layers offset downward
    Rectangle { anchors.fill: bgRect; anchors.topMargin: 3; anchors.bottomMargin: -3
        radius: bgRect.radius + 1; color: Qt.rgba(15/255, 23/255, 42/255, 0.035) }
    Rectangle { anchors.fill: bgRect; anchors.topMargin: 1; anchors.bottomMargin: -1
        radius: bgRect.radius; color: Qt.rgba(15/255, 23/255, 42/255, 0.05) }
    Rectangle {
        id: bgRect
        anchors.fill: parent
        radius: Theme.radius
        color: Theme.surface
        border.color: Theme.border
        border.width: 1
    }
    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
