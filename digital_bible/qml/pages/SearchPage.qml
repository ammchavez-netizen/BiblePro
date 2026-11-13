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
            spacing: Theme.s(8)
            AppTextField {
                id: query
                Layout.fillWidth: true
                implicitHeight: Theme.s(38)
                placeholderText: "Search words or a \"phrase\"…"
                ToolTip.visible: hovered && text === ""; ToolTip.delay: 700
                ToolTip.text: "All words must match. Put an exact phrase in \"quotes\"."
                onAccepted: ctrl.search(text, scope.currentIndex)
            }
            AppComboBox {
                id: scope
                Layout.preferredWidth: Theme.s(150)
                implicitHeight: Theme.s(38)
                model: ["Whole Bible", "Old Testament", "New Testament", "Current book"]
            }
            AppButton { text: "Search"; iconName: "search"; variant: "primary"; implicitHeight: Theme.s(38); font.pixelSize: Theme.s(14)
                        onClicked: ctrl.search(query.text, scope.currentIndex) }
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
            spacing: Theme.s(2)
            model: ctrl.searchResults
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: item
                required property var modelData
                width: ListView.view.width
                height: Math.max(40, body.implicitHeight + 16)
                radius: Theme.s(6)
                color: ma.containsMouse ? Theme.accentSoft : "transparent"
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.s(8)
                    spacing: Theme.s(12)
                    Text {
                        Layout.preferredWidth: Theme.s(130)
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
            Column {
                anchors.centerIn: parent
                visible: results.count === 0
                spacing: Theme.s(10)
                Icon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: results.height > Theme.s(150)
                    name: "book"; size: Theme.s(56); strokeWidth: 1.6
                    color: "#8DB1F7"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ctrl.searchInfo !== "" ? "No matches" : "No results yet"
                    font.family: Theme.font; font.pixelSize: Theme.s(21); font.weight: Font.Medium
                    color: Theme.text
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ctrl.searchInfo !== "" ? "Try fewer or different words." : "Enter a word or phrase above to search the Bible."
                    font.family: Theme.font; font.pixelSize: Theme.s(14)
                    color: "#2F4A9C"
                }
            }
        }
    }
}
