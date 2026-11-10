import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// Verses shown before, in the version they were shown in.
Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.gap
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "Click to show again (in the version it was shown in)."
                font.family: Theme.font; font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
            }
            AppButton { text: "Clear history"; compact: true; variant: "danger"; onClicked: ctrl.clearHistory() }
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: ctrl.history
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: item
                required property var modelData
                width: ListView.view.width
                height: 36
                radius: 6
                color: ma.containsMouse ? Theme.accentSoft : "transparent"
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    Text {
                        Layout.fillWidth: true
                        text: item.modelData.reference
                        font.family: Theme.font; font.pixelSize: Theme.fontSize; font.weight: Font.Medium
                        color: Theme.text
                    }
                    Text {
                        text: item.modelData.abbr
                        font.family: Theme.font; font.pixelSize: Theme.fontSmall; font.weight: Font.DemiBold
                        color: Theme.accent
                    }
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: ctrl.openHistory(item.modelData.index)
                }
            }
            Text {
                anchors.centerIn: parent
                visible: list.count === 0
                text: "Nothing shown yet"
                font.family: Theme.font; font.pixelSize: Theme.fontSize
                color: Theme.textFaint
            }
        }
    }
}
