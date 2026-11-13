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
                text: "Verses shown since BibleQ-AI was opened. Click to show one again (in the version it was shown in)."
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
            spacing: Theme.s(2)
            model: ctrl.history
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: item
                required property var modelData
                width: ListView.view.width
                height: Theme.s(36)
                radius: Theme.s(6)
                color: ma.containsMouse ? Theme.accentSoft : "transparent"
                // one line per verse: reference, the verse text (shortened with …), version
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.s(10)
                    anchors.rightMargin: Theme.s(10)
                    spacing: Theme.s(12)
                    Text {
                        Layout.preferredWidth: Math.min(implicitWidth, Theme.s(170))
                        text: item.modelData.reference
                        font.family: Theme.font; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                        color: Theme.accent
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: item.modelData.text
                        font.family: Theme.font; font.pixelSize: Theme.fontSize
                        color: Theme.textFaint
						font.italic: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        wrapMode: Text.NoWrap
                    }
                    Text {
                        text: item.modelData.abbr
                        font.family: Theme.font; font.pixelSize: Theme.fontSmall; font.weight: Font.DemiBold
                        color: Theme.textMuted
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
