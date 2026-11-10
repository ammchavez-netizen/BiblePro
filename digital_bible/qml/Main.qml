import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BiblePro.Native
import "components"
import "pages"

ApplicationWindow {
    id: win
    title: "BiblePro"
    width: 1240
    height: 820
    minimumWidth: 720
    minimumHeight: 560
    visible: true
    color: Theme.bg
    font.family: Theme.font
    font.pixelSize: Theme.fontSize

    readonly property bool wide: width >= 1080

    Component.onCompleted: {
        var g = ctrl.windowGeometry()
        if (g.length === 4 && g[2] >= minimumWidth && g[3] >= minimumHeight) {
            x = g[0]; y = g[1]; width = g[2]; height = g[3]
        }
        refField.forceActiveFocus()
    }
    onClosing: { aiCtrl.setChatPoppedOut(false); ctrl.saveWindowGeometry(x, y, width, height); ctrl.shutdown() }

    // ------------------------------------------------------------ pop-out AI chat
    // Same size as this window, placed on its right side; it follows this window
    // when it is moved or resized.
    function dockChat() { if (chatWin.visible) aiCtrl.dockWindow(chatWin, win) }
    onXChanged: dockTimer.restart()
    onYChanged: dockTimer.restart()
    onWidthChanged: dockTimer.restart()
    onHeightChanged: dockTimer.restart()
    Timer { id: dockTimer; interval: 60; onTriggered: win.dockChat() }

    Window {
        id: chatWin
        title: "BiblePro — AI Chat"
        visible: aiCtrl.chatPoppedOut
        color: Theme.bg
        minimumWidth: 420
        minimumHeight: 420
        onVisibleChanged: if (visible) { win.dockChat(); dockTimer.restart(); chatPanelPop.focusInput() }
        onClosing: aiCtrl.setChatPoppedOut(false)
        ChatPanel {
            id: chatPanelPop
            anchors.fill: parent
            anchors.margins: 16
            popout: true
            onDockRequested: { aiCtrl.setChatPoppedOut(false); win.raise(); win.requestActivate() }
        }
    }

    Connections {
        target: ctrl
        function onFocusReference(ch) {
            win.raise(); win.requestActivate()
            if (ch !== "") refField.text = ch
            refField.forceActiveFocus()
            if (ch === "") refField.selectAll()
        }
        function onReferenceChanged() { refField.text = ctrl.referenceText; refField.selectAll() }
        function onImportChanged() { if (!ctrl.importState.running && ctrl.importState.text !== "") toast.show(ctrl.importState.text) }
    }

    // ------------------------------------------------------------ shortcuts
    Shortcut { sequences: ["PgDown", "Ctrl+Right", "Alt+Right"]; onActivated: ctrl.next() }
    Shortcut { sequences: ["PgUp", "Ctrl+Left", "Alt+Left"]; onActivated: ctrl.prev() }
    Shortcut { sequence: "Ctrl+K"; onActivated: picker.open() }
    Shortcut { sequence: "Ctrl+F"; onActivated: { tabs.currentIndex = 0; searchPage.focusSearch() } }
    Shortcut { sequences: ["Ctrl+L", "Esc"]; onActivated: { refField.forceActiveFocus(); refField.selectAll() } }
    Shortcut { sequence: "Ctrl+B"; onActivated: ctrl.toggleBlank() }
    Shortcut { sequence: "Ctrl+D"; onActivated: ctrl.setDisplayVisible(!ctrl.displayState.visible) }
    Shortcut { sequence: "F11"; onActivated: ctrl.toggleFullscreen() }
    Shortcut { sequence: "Ctrl+1"; onActivated: ctrl.favoriteN(1) }
    Shortcut { sequence: "Ctrl+2"; onActivated: ctrl.favoriteN(2) }
    Shortcut { sequence: "Ctrl+3"; onActivated: ctrl.favoriteN(3) }
    Shortcut { sequence: "Ctrl+4"; onActivated: ctrl.favoriteN(4) }
    Shortcut { sequence: "Ctrl+5"; onActivated: ctrl.favoriteN(5) }
    Shortcut { sequence: "Ctrl+6"; onActivated: ctrl.favoriteN(6) }
    Shortcut { sequence: "Ctrl+7"; onActivated: ctrl.favoriteN(7) }
    Shortcut { sequence: "Ctrl+8"; onActivated: ctrl.favoriteN(8) }
    Shortcut { sequence: "Ctrl+9"; onActivated: ctrl.favoriteN(9) }

    // ------------------------------------------------------------ header
    header: Rectangle {
        height: 56
        color: Theme.surface
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 12
            spacing: 10
            Image { source: iconUrl; sourceSize: Qt.size(30, 30); Layout.preferredWidth: 30; Layout.preferredHeight: 30 }
            Text {
                text: "BiblePro"
                font.family: Theme.font; font.pixelSize: Theme.fontTitle; font.weight: Font.Bold
                color: Theme.text
            }
            Text {
                text: ctrl.about.version
                font.family: Theme.font; font.pixelSize: Theme.fontSmall
                color: Theme.textFaint
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: 18
            }
            Item { Layout.fillWidth: true }
            // import progress
            RowLayout {
                visible: ctrl.importState.running
                spacing: 8
                Text { text: ctrl.importState.text; color: Theme.textMuted; font.pixelSize: Theme.fontSmall; elide: Text.ElideRight; Layout.maximumWidth: 260 }
                ProgressBar { Layout.preferredWidth: 140; from: 0; to: Math.max(1, ctrl.importState.total); value: ctrl.importState.value }
                AppButton { text: "Cancel"; compact: true; onClicked: ctrl.cancelImport() }
            }
            AppButton { text: "Import Bible Version…"; variant: "ghost"; onClicked: ctrl.importBibles(); enabled: !ctrl.importState.running }
            AppButton {
                id: moreBtn
                text: "⋯"
                variant: "ghost"
                implicitWidth: 40
                font.pixelSize: 18
                onClicked: moreMenu.popup(moreBtn, 0, moreBtn.height)
                Menu {
                    id: moreMenu
                    MenuItem { text: "Open data folder"; onTriggered: ctrl.openDataFolder() }
                    MenuItem { text: "Keyboard shortcuts"; onTriggered: shortcutsDlg.open() }
                    MenuSeparator {}
                    MenuItem { text: "About BiblePro"; onTriggered: aboutDlg.open() }
                }
            }
        }
    }

    // ------------------------------------------------------------ body
    GridLayout {
        id: body
        anchors.fill: parent
        anchors.margins: 16
        columns: win.wide ? 2 : 1
        columnSpacing: 16
        rowSpacing: 16
        visible: ctrl.hasLibrary

        // ======== left column: entry, version, preview
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: win.wide ? win.width * 0.47 : -1
            Layout.maximumWidth: win.wide ? win.width * 0.52 : 100000
            spacing: 16

            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: entryCol.implicitHeight + 32
                ColumnLayout {
                    id: entryCol
                    width: parent.width
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        AppButton {
                            text: "‹"; font.pixelSize: 28; font.weight: Font.Bold
                            implicitWidth: 52; implicitHeight: 46
                            onClicked: ctrl.prev()
                            ToolTip.visible: hovered; ToolTip.text: "Previous verse (PgUp)"; ToolTip.delay: 500
                        }
                        AppTextField {
                            id: refField
                            Layout.fillWidth: true
                            implicitHeight: 46
                            font.pixelSize: 18
                            placeholderText: "Type a verse — e.g. Juan 3:16, jn 3:16-18, 1 pe 5:7"
                            onAccepted: ctrl.go(text)
                        }
                        AppButton {
                            text: "›"; font.pixelSize: 28; font.weight: Font.Bold
                            implicitWidth: 52; implicitHeight: 46
                            onClicked: ctrl.next()
                            ToolTip.visible: hovered; ToolTip.text: "Next verse (PgDn)"; ToolTip.delay: 500
                        }
                        AppButton { text: "Show"; variant: "primary"; implicitHeight: 46; onClicked: ctrl.go(refField.text) }
                    }
                    Text {
                        visible: ctrl.message !== ""
                        text: ctrl.message
                        color: Theme.danger
                        font.family: Theme.font; font.pixelSize: Theme.fontSmall
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        AbstractButton {
                            id: versionBtn
                            Layout.fillWidth: true
                            implicitHeight: 40
                            hoverEnabled: true
                            onClicked: picker.open()
                            ToolTip.visible: hovered; ToolTip.text: "Change version (Ctrl+K)"; ToolTip.delay: 600
                            background: Rectangle {
                                radius: Theme.radiusSmall
                                color: versionBtn.hovered ? "#F1F5FF" : Theme.accentSoft
                                border.color: "#C7D7FE"
                            }
                            contentItem: RowLayout {
                                spacing: 10
                                Text {
                                    Layout.leftMargin: 12
                                    text: ctrl.currentVersion.abbr || "—"
                                    font.family: Theme.font; font.pixelSize: Theme.fontLarge; font.weight: Font.Bold
                                    color: Theme.accent
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: (ctrl.currentVersion.name || "") + "  ·  " + (ctrl.currentVersion.language || "")
                                          + (ctrl.currentVersion.coverage ? "  ·  " + ctrl.currentVersion.coverage : "")
                                    font.family: Theme.font; font.pixelSize: Theme.fontSize
                                    color: Theme.text
                                    elide: Text.ElideRight
                                }
                                Text { Layout.rightMargin: 12; text: "▾"; color: Theme.accent; font.pixelSize: 14 }
                            }
                        }
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Text { text: "Favorites"; color: Theme.textMuted; font.pixelSize: Theme.fontSmall; height: 28; verticalAlignment: Text.AlignVCenter; rightPadding: 4 }
                        Repeater {
                            model: ctrl.favorites
                            delegate: Chip {
                                required property var modelData
                                required property int index
                                text: modelData.abbr
                                selected: modelData.code === ctrl.currentVersion.code
                                hint: modelData.name + (index < 9 ? "   (Ctrl+" + (index + 1) + ")" : "")
                                onClicked: ctrl.setVersion(modelData.code)
                            }
                        }
                    }
                }
            }

            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 260
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        SectionLabel { text: "On screen now" }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: ctrl.blank ? "Blank" : ctrl.slideInfo.reference
                            font.family: Theme.font; font.pixelSize: Theme.fontSmall; font.weight: Font.DemiBold
                            color: ctrl.blank ? Theme.warning : Theme.textMuted
                        }
                    }
                    SlidePreview {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 120
                        controller: ctrl
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        AppButton {
                            text: ctrl.displayState.visible ? "Hide display" : "Show display"
                            onClicked: ctrl.setDisplayVisible(!ctrl.displayState.visible)
                        }
                        AppButton {
                            id: fsBtn
                            text: ctrl.displayState.fullscreen ? "Fullscreen ✓ ▾" : "Fullscreen on… ▾"
                            onClicked: fsMenu.popup(fsBtn, 0, fsBtn.height)
                            Menu {
                                id: fsMenu
                                Repeater {
                                    model: ctrl.displayState.screens
                                    delegate: MenuItem {
                                        required property var modelData
                                        text: modelData.label
                                        onTriggered: ctrl.fullscreenOn(modelData.name)
                                    }
                                }
                                MenuSeparator {}
                                MenuItem { text: "Windowed (not fullscreen)"; onTriggered: ctrl.leaveFullscreen() }
                            }
                        }
                        AppButton {
                            text: "Blank"
                            checkable: true
                            checked: ctrl.blank
                            onClicked: ctrl.toggleBlank()
                            ToolTip.visible: hovered; ToolTip.text: "Black screen (Ctrl+B)"; ToolTip.delay: 500
                        }
                        AppSwitch { text: "Borderless"; checked: ctrl.displayState.frameless; onToggled: ctrl.setFrameless(checked) }
                        AppSwitch { text: "Always on top"; checked: ctrl.displayState.onTop; onToggled: ctrl.setOnTop(checked) }
                    }
                }
            }
        }

        // ======== right column: tabs
        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 320
            padding: 0
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                TabBar {
                    id: tabs
                    objectName: "tabs"
                    Layout.fillWidth: true
                    Layout.leftMargin: 12
                    Layout.topMargin: 6
                    background: Item {}
                    Repeater {
                        model: ["Search", "History", "Appearance", "AI Mode"]
                        delegate: TabButton {
                            required property string modelData
                            required property int index
                            text: modelData
                            width: implicitWidth + 16
                            font.family: Theme.font; font.pixelSize: Theme.fontSize
                            font.weight: tabs.currentIndex === index ? Font.DemiBold : Font.Normal
                            contentItem: Text {
                                text: parent.text
                                font: parent.font
                                color: tabs.currentIndex === index ? Theme.accent : Theme.textMuted
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: "transparent"
                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width; height: 2
                                    color: tabs.currentIndex === index ? Theme.accent : "transparent"
                                }
                            }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 16
                    currentIndex: tabs.currentIndex
                    SearchPage { id: searchPage }
                    HistoryPage {}
                    AppearancePage {}
                    Loader {
                        id: aiLoader
                        active: tabs.currentIndex === 3 || item !== null
                        source: "pages/AiPage.qml"
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ first run
    Card {
        visible: !ctrl.hasLibrary
        anchors.centerIn: parent
        width: Math.min(520, parent.width - 40)
        height: emptyCol.implicitHeight + 48
        padding: 24
        ColumnLayout {
            id: emptyCol
            width: parent.width
            spacing: 12
            Text { text: "Welcome to BiblePro"; font.pixelSize: Theme.fontTitle; font.weight: Font.Bold; color: Theme.text }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Theme.textMuted
                text: "No Bibles are installed yet. Import them from the old Digital Bible app: choose the folder that contains its “Bibles” and “Images” folders."
            }
            AppButton { text: "Import Bible Version…"; variant: "primary"; onClicked: ctrl.importBibles(); enabled: !ctrl.importState.running }
        }
    }

    VersionPicker {
        id: picker
        objectName: "picker"
        anchors.centerIn: parent
        width: Math.min(640, win.width - 60)
        height: Math.min(560, win.height - 80)
        onChosen: (code) => ctrl.setVersion(code)
    }

    // ------------------------------------------------------------ dialogs
    Dialog {
        id: aboutDlg
        objectName: "aboutDialog"
        anchors.centerIn: parent
        modal: true
        title: ""
        standardButtons: Dialog.Ok
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        ColumnLayout {
            spacing: 6
            RowLayout {
                spacing: 12
                Image { source: iconUrl; sourceSize: Qt.size(56, 56) }
                ColumnLayout {
                    spacing: 0
                    Text { text: ctrl.about.app; font.pixelSize: 22; font.weight: Font.Bold; color: Theme.text }
                    Text { text: "Version " + ctrl.about.version; color: Theme.textMuted }
                }
            }
            Text { text: ctrl.about.description; color: Theme.text; Layout.topMargin: 8; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.maximumWidth: 420 }
            Text { text: ctrl.about.author; font.weight: Font.DemiBold; color: Theme.text; Layout.topMargin: 8 }
            Text { text: ctrl.about.locale; color: Theme.text }
            Text {
                text: "<a href='mailto:" + ctrl.about.email + "'>" + ctrl.about.email + "</a>"
                textFormat: Text.RichText
                linkColor: Theme.accent
                onLinkActivated: (link) => Qt.openUrlExternally(link)
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
            Text { text: ctrl.about.versions + " Bible versions installed"; color: Theme.textFaint; Layout.topMargin: 8 }
        }
    }

    Dialog {
        id: shortcutsDlg
        anchors.centerIn: parent
        modal: true
        title: "Keyboard shortcuts"
        standardButtons: Dialog.Ok
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        GridLayout {
            columns: 2
            columnSpacing: 24
            rowSpacing: 6
            Repeater {
                model: [
                    ["Enter", "Show the typed reference"], ["PgDn / Ctrl+→", "Next verse"],
                    ["PgUp / Ctrl+←", "Previous verse"], ["Ctrl+K", "Choose version"],
                    ["Ctrl+1…9", "Favorite versions"], ["Ctrl+F", "Search text"],
                    ["Ctrl+L / Esc", "Go to the reference box"], ["Ctrl+B", "Blank screen"],
                    ["Ctrl+D", "Show/hide display"], ["F11", "Display fullscreen on/off"],
                    ["On the display", "→ ← next/previous · F11 fullscreen · B blank · right-click options"]
                ]
                delegate: Text {
                    required property var modelData
                    required property int index
                    text: modelData[0] + "\t" + modelData[1]
                    color: Theme.text
                    Layout.columnSpan: 2
                }
            }
        }
    }

    // ------------------------------------------------------------ toast
    Rectangle {
        id: toast
        property string msg: ""
        function show(m) { msg = m; opacity = 1; toastTimer.restart() }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        width: toastText.implicitWidth + 32
        height: 40
        radius: 20
        color: "#1E293B"
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; text: toast.msg; color: "white"; font.pixelSize: Theme.fontSize }
        Timer { id: toastTimer; interval: 4000; onTriggered: toast.opacity = 0 }
    }
}
