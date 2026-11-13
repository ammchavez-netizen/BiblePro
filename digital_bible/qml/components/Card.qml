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
    Rectangle { anchors.fill: bgRect; anchors.margins: -2; anchors.topMargin: Theme.s(4); anchors.bottomMargin: -6
        radius: bgRect.radius + 3; color: Qt.rgba(30/255, 60/255, 140/255, 0.035) }
    Rectangle { anchors.fill: bgRect; anchors.topMargin: Theme.s(2); anchors.bottomMargin: -2
        radius: bgRect.radius; color: Qt.rgba(30/255, 60/255, 140/255, 0.05) }
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
