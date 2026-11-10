import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// Text search in the selected version.
Item {
    id: root
    function focusSearch() { query.forceActiveFocus(); query.selectAll() }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.gap
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField {
                id: query
                Layout.fillWidth: true
                placeholderText: "Search words…   (all words must match; \"quotes\" for an exact phrase)"
                onAccepted: ctrl.search(text, scope.currentIndex)
            }
            AppComboBox {
                id: scope
                Layout.preferredWidth: 190
                model: ["Whole Bible", "Old Testament", "New Testament", "Current book"]
            }
            AppButton { text: "Search"; variant: "primary"; onClicked: ctrl.search(query.text, scope.currentIndex) }
        }
        Text {
            Layout.fillWidth: true
            text: ctrl.searchInfo !== "" ? ctrl.searchInfo + ". Click a result to show it."
                                         : "Results come from the selected version."
            font.family: Theme.font; font.pixelSize: Theme.fontSmall
            color: Theme.textMuted
            wrapMode: Text.Wrap
        }
        ListView {
            id: results
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: ctrl.searchResults
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: item
                required property var modelData
                width: ListView.view.width
                height: Math.max(40, body.implicitHeight + 16)
                radius: 6
                color: ma.containsMouse ? Theme.accentSoft : "transparent"
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 130
                        Layout.alignment: Qt.AlignTop
                        text: item.modelData.reference
                        font.family: Theme.font; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                        color: Theme.accent
                        elide: Text.ElideRight
                    }
                    Text {
                        id: body
                        Layout.fillWidth: true
                        text: item.modelData.text
                        font.family: Theme.font; font.pixelSize: Theme.fontSize
                        color: Theme.text
                        wrapMode: Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: ctrl.showKey(item.modelData.key)
                }
            }
            Text {
                anchors.centerIn: parent
                visible: results.count === 0
                text: "No results yet"
                font.family: Theme.font; font.pixelSize: Theme.fontSize
                color: Theme.textFaint
            }
        }
    }
}
