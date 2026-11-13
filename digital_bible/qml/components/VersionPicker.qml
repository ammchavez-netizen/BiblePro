import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Popup list of all Bible versions: type to filter, grouped by language,
// click the star to add/remove a favorite.
Popup {
    id: root
    signal chosen(string code)
    width: Theme.s(620)
    height: Theme.s(540)
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    property string filterText: ""
    readonly property var filtered: {
        var q = filterText.toLowerCase().trim()
        var words = q.length ? q.split(/\s+/) : []
        var favs = ctrl ? ctrl.favoriteCodes : []
        var all = ctrl ? ctrl.versions : []
        var out = []
        if (!q) {
            for (var f = 0; f < favs.length; f++)
                for (var j = 0; j < all.length; j++)
                    if (all[j].code === favs[f]) { var c = Object.assign({}, all[j]); c.group = "★ Favorites"; out.push(c) }
        }
        for (var i = 0; i < all.length; i++) {
            var v = all[i]
            var hay = (v.abbr + " " + v.name + " " + v.language + " " + v.coverage).toLowerCase()
            var ok = true
            for (var w = 0; w < words.length; w++) if (hay.indexOf(words[w]) < 0) { ok = false; break }
            if (ok) { var d = Object.assign({}, v); d.group = v.language; out.push(d) }
        }
        return out
    }

    onOpened: { filterText = ""; field.text = ""; field.forceActiveFocus(); list.currentIndex = 0 }

    background: Rectangle {
        radius: Theme.radius
        color: Theme.surface
        border.color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.s(14)
        spacing: Theme.s(10)

        Text {
            text: "Choose a Bible version"
            font.family: Theme.font; font.pixelSize: Theme.fontLarge; font.weight: Font.DemiBold
            color: Theme.text
        }
        AppTextField {
            id: field
            Layout.fillWidth: true
            placeholderText: "Filter by name, abbreviation or language — e.g. tagalog, kjv, reina"
            onTextChanged: { root.filterText = text; list.currentIndex = 0 }
            Keys.onDownPressed: list.incrementCurrentIndex()
            Keys.onUpPressed: list.decrementCurrentIndex()
            Keys.onReturnPressed: root.pickCurrent()
            Keys.onEnterPressed: root.pickCurrent()
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.filtered
            highlightMoveDuration: 0
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            section.property: "group"
            section.criteria: ViewSection.FullString
            section.delegate: Rectangle {
                width: ListView.view.width
                height: Theme.s(30)
                color: Theme.surface
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 6
                    text: section
                    font.family: Theme.font; font.pixelSize: Theme.fontSmall; font.weight: Font.Bold
                    color: section.indexOf("★") === 0 ? Theme.gold : Theme.textMuted
                }
            }
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                width: ListView.view.width
                height: Theme.s(38)
                radius: Theme.s(6)
                readonly property bool isCurrent: ctrl && modelData.code === ctrl.currentVersion.code
                color: ListView.isCurrentItem ? Theme.accentSoft : hover.hovered ? "#F8FAFC" : "transparent"
                HoverHandler { id: hover }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.s(4)
                    anchors.rightMargin: Theme.s(10)
                    spacing: Theme.s(8)
                    AbstractButton {
                        Layout.preferredWidth: Theme.s(30); Layout.fillHeight: true
                        onClicked: ctrl.toggleFavorite(row.modelData.code)
                        contentItem: Text {
                            text: ctrl && ctrl.favoriteCodes.indexOf(row.modelData.code) >= 0 ? "★" : "☆"
                            color: text === "★" ? Theme.gold : Theme.textFaint
                            font.pixelSize: Theme.s(17)
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                        ToolTip.visible: hovered; ToolTip.text: "Add to / remove from favorites"; ToolTip.delay: 600
                    }
                    Text {
                        Layout.preferredWidth: Theme.s(92)
                        text: row.modelData.abbr
                        font.family: Theme.font; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                        color: Theme.accent
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: row.modelData.name
                        font.family: Theme.font; font.pixelSize: Theme.fontSize
                        font.weight: row.isCurrent ? Font.Bold : Font.Normal
                        color: Theme.text
                        elide: Text.ElideRight
                    }
                    Text {
                        text: row.modelData.coverage
                        visible: text !== ""
                        font.family: Theme.font; font.pixelSize: Theme.fontSmall
                        color: Theme.textMuted
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.s(34)
                    onClicked: root.pick(row.modelData.code)
                }
            }
        }
        Text {
            text: "Enter or click to use • ★ adds a favorite (Ctrl+1…9)"
            font.family: Theme.font; font.pixelSize: Theme.fontSmall
            color: Theme.textMuted
        }
    }

    function pick(code) { root.chosen(code); root.close() }
    function pickCurrent() {
        if (list.currentIndex >= 0 && list.currentIndex < root.filtered.length)
            pick(root.filtered[list.currentIndex].code)
    }
}
