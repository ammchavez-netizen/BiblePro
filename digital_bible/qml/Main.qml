import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BibleQ.Native
import "components"
import "pages"

ApplicationWindow {
    id: win
    title: "BibleQ-AI"
    width: 960
    height: 820
    minimumWidth: 720
    minimumHeight: 600
    visible: true
    color: Theme.bg
    font.family: Theme.font
    font.pixelSize: Theme.fontSize

    // Everything (text, icons, boxes, buttons) grows and shrinks with the window.
    function updateScale() {
        var k = Math.max(0.78, Math.min(1.4, Math.min(win.width / 960, win.height / 820)))
        if (Math.abs(k - Theme.scale) > 0.004) Theme.scale = k
    }
    Timer { id: scaleTimer; interval: 30; onTriggered: win.updateScale() }
    property bool settingsOpen: false            // a Settings page is shown in the bottom card
    property string settingsPage: "appearance"   // "appearance" | "ai"
    function openTab(i) { win.settingsOpen = false; tabs.currentIndex = i }
    function openSettings(page) { win.settingsPage = page; win.settingsOpen = true }

    Component.onCompleted: {
        var g = ctrl.windowGeometry()
        if (g.length === 4 && g[2] >= minimumWidth && g[3] >= minimumHeight) {
            x = g[0]; y = g[1]; width = g[2]; height = g[3]
        }
        updateScale()
        refField.forceActiveFocus()
    }
    onClosing: { aiCtrl.setChatPoppedOut(false); ctrl.saveWindowGeometry(x, y, width, height); ctrl.shutdown() }

    // ------------------------------------------------------------ pop-out AI chat
    // Same size as this window, placed on its right side; it follows this window
    // when it is moved or resized.
    function dockChat() { if (chatWin.visible) aiCtrl.dockWindow(chatWin, win) }
    onXChanged: dockTimer.restart()
    onYChanged: dockTimer.restart()
    onWidthChanged: { dockTimer.restart(); scaleTimer.restart() }
    onHeightChanged: { dockTimer.restart(); scaleTimer.restart() }
    Timer { id: dockTimer; interval: 60; onTriggered: win.dockChat() }

    Window {
        id: chatWin
        title: "BibleQ-AI — AI Chat"
        visible: aiCtrl.chatPoppedOut
        color: Theme.bg
        minimumWidth: 420
        minimumHeight: 420
        onVisibleChanged: if (visible) { win.dockChat(); dockTimer.restart(); chatPanelPop.focusInput() }
        onClosing: aiCtrl.setChatPoppedOut(false)
        ChatPanel {
            id: chatPanelPop
            anchors.fill: parent
            anchors.margins: Theme.s(16)
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
        function onToast(msg) { toast.show(msg) }
        function onImportChanged() { if (!ctrl.importState.running && ctrl.importState.text !== "") toast.show(ctrl.importState.text) }
    }

    // ------------------------------------------------------------ shortcuts
    Shortcut { sequences: ["PgDown", "Ctrl+Right", "Alt+Right"]; onActivated: ctrl.next() }
    Shortcut { sequences: ["PgUp", "Ctrl+Left", "Alt+Left"]; onActivated: ctrl.prev() }
    Shortcut { sequence: "Ctrl+K"; onActivated: picker.open() }
    Shortcut { sequence: "Ctrl+F"; onActivated: { win.openTab(0); searchPage.focusSearch() } }
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

    // ------------------------------------------------------------ background
    background: Rectangle {
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.bgTop }
            GradientStop { position: 1.0; color: Theme.bgBottom }
        }
    }

    // ------------------------------------------------------------ sidebar
    readonly property bool compactNav: width < 800
    Rectangle {
        id: sidebar
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: Theme.s(win.compactNav ? 64 : 156)
        color: "transparent"
        WavyBackground { anchors.fill: parent }
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.border }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.s(12)
            anchors.topMargin: Theme.s(20)
            spacing: Theme.s(6)

            // logo + name + version
            Image {
                Layout.alignment: Qt.AlignHCenter
                source: iconUrl
                sourceSize: Qt.size(Theme.s(win.compactNav ? 40 : 56), Theme.s(win.compactNav ? 40 : 56))
                Layout.preferredWidth: Theme.s(win.compactNav ? 40 : 56)
                Layout.preferredHeight: Theme.s(win.compactNav ? 40 : 56)
                smooth: true
            }
            Text {
                visible: !win.compactNav
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Theme.s(4)
                text: "BibleQ-AI"
                font.family: Theme.font; font.pixelSize: Theme.s(18); font.weight: Font.Bold
                color: Theme.navy
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: ctrl.about.version
                font.family: Theme.font; font.pixelSize: Theme.s(12)
                color: Theme.textMuted
            }
            Item { Layout.preferredHeight: Theme.s(14) }

            Repeater {
                model: [["Search", "search"], ["History", "history"], ["AI Mode", "sparkle"]]
                delegate: NavButton {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    text: modelData[0]
                    iconName: modelData[1]
                    compact: win.compactNav
                    selected: !win.settingsOpen && tabs.currentIndex === index
                    onClicked: win.openTab(index)
                }
            }

            Item { Layout.fillHeight: true }

            // import progress
            ColumnLayout {
                visible: ctrl.importState.running
                Layout.fillWidth: true
                spacing: Theme.s(6)
                Text {
                    Layout.fillWidth: true
                    text: ctrl.importState.text
                    color: Theme.textMuted; font.pixelSize: Theme.fontSmall
                    wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
                }
                ProgressBar { Layout.fillWidth: true; from: 0; to: Math.max(1, ctrl.importState.total); value: ctrl.importState.value }
                AppButton { text: "Cancel import"; compact: true; onClicked: ctrl.cancelImport() }
            }

            Rectangle { Layout.fillWidth: true; Layout.leftMargin: Theme.s(8); Layout.rightMargin: Theme.s(8); height: 1; color: Theme.border }
            NavButton {
                id: settingsBtn
                Layout.fillWidth: true
                text: "Settings"
                iconName: "settings"
                compact: win.compactNav
                selected: win.settingsOpen
                onClicked: settingsMenu.popup(settingsBtn, settingsBtn.width + Theme.s(8),
                                              settingsBtn.height - settingsMenu.implicitHeight)
                Menu {
                    id: settingsMenu
                    MenuItem { text: "Appearance"; onTriggered: win.openSettings("appearance") }
                    MenuItem { text: "AI Mode Settings"; onTriggered: win.openSettings("ai") }
                    MenuItem { text: "Keyboard shortcuts"; onTriggered: shortcutsDlg.open() }
                    MenuSeparator {}
                    MenuItem {
                        objectName: "importVersionItem"
                        text: "Import Bible version…"
                        enabled: !ctrl.importState.running
                        onTriggered: ctrl.importVersionFiles()
                    }
                }
            }
            NavButton {
                Layout.fillWidth: true
                text: "About"
                iconName: "info"
                compact: win.compactNav
                onClicked: aboutDlg.open()
            }
        }
    }

    // ------------------------------------------------------------ body
    // Compact, stacked: reference entry, "On screen now" (preview | arrows | controls), tabs.
    ColumnLayout {
        id: body
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.left: sidebar.right
        anchors.margins: Theme.s(14)
        spacing: Theme.s(12)
        visible: ctrl.hasLibrary

        // ======== reference entry + version
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: entryCol.implicitHeight + 2 * padding
            padding: Theme.s(12)
            ColumnLayout {
                id: entryCol
                width: parent.width
                spacing: Theme.s(10)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.s(8)
                    AppTextField {
                        id: refField
                        Layout.fillWidth: true
                        Layout.preferredWidth: Theme.s(280)
                        Layout.maximumWidth: Theme.s(420)
                        implicitHeight: Theme.s(36)
                        font.pixelSize: Theme.s(15)
                        leftPadding: Theme.s(12)
                        placeholderText: "Type a verse — e.g. jn 3:16"
                        onAccepted: ctrl.go(text)
                        ToolTip.visible: hovered && text === ""; ToolTip.delay: 800
                        ToolTip.text: "Juan 3:16, jn 3:16-18, 1 pe 5:7, Awit 23 … then Enter"
                    }
                    AppButton {
                        text: "Show"
                        iconName: "search"
                        variant: "primary"
                        implicitHeight: Theme.s(36)
                        leftPadding: Theme.s(16); rightPadding: Theme.s(16)
                        font.pixelSize: Theme.s(14)
                        onClicked: ctrl.go(refField.text)
                    }
                    Item { Layout.fillWidth: true; Layout.minimumWidth: Theme.s(8) }
                    AbstractButton {
                        id: versionBtn
                        implicitHeight: Theme.s(34)
                        implicitWidth: vRow.implicitWidth + Theme.s(22)
                        hoverEnabled: true
                        onClicked: picker.open()
                        ToolTip.visible: hovered; ToolTip.text: "Change version (Ctrl+K)"; ToolTip.delay: 600
                        background: Rectangle {
                            radius: Theme.radiusSmall
                            color: versionBtn.hovered ? "#F2F6FE" : Theme.surface
                            border.color: Theme.accentBorder
                        }
                        contentItem: Item {
                            Row {
                                id: vRow
                                anchors.centerIn: parent
                                spacing: Theme.s(8)
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: ctrl.currentVersion.abbr || "—"
                                    font.family: Theme.font; font.pixelSize: Theme.s(14); font.weight: Font.Bold
                                    color: Theme.accent
                                }
                                Icon { anchors.verticalCenter: parent.verticalCenter; name: "chevron-down"; size: Theme.s(14); strokeWidth: 2.6; color: Theme.accent }
                            }
                        }
                    }
                    Text {
                        Layout.maximumWidth: Theme.s(240)
                        text: (ctrl.currentVersion.name || "") + "  •  " + (ctrl.currentVersion.language || "")
                        font.family: Theme.font; font.pixelSize: Theme.s(13)
                        color: Theme.textMuted
                        elide: Text.ElideRight
                        ToolTip.visible: vNameHover.hovered && truncated; ToolTip.text: text
                        HoverHandler { id: vNameHover }
                    }
                }
                Text {
                    visible: ctrl.message !== ""
                    text: ctrl.message
                    color: Theme.danger
                    font.family: Theme.font; font.pixelSize: Theme.fontSmall
                }
                Flow {
                    visible: ctrl.favorites.length > 0
                    Layout.fillWidth: true
                    spacing: Theme.s(8)
                    Text {
                        height: Theme.s(28)
                        verticalAlignment: Text.AlignVCenter
                        text: "Favorites:"
                        font.family: Theme.font; font.pixelSize: Theme.s(13)
                        color: Theme.textMuted
                    }
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

        // ======== on screen now:  preview | ◀ ▶ | display controls
        Card {
            id: screenCard
            Layout.fillWidth: true
            padding: Theme.s(12)
            // The preview fills the width left over by the arrows and controls (in the display's
            // shape), but never takes more than ~45% of the height and never less than the controls.
            readonly property real previewW: width - 2 * padding - navCol.implicitWidth - ctlCol.width - 3 * screenRow.spacing
            readonly property real wantH: screenHead.implicitHeight + Theme.s(8) + previewW / Math.max(0.5, ctrl.displayState.aspect || 16 / 9)
            Layout.preferredHeight: Math.max(ctlCol.implicitHeight + ctlCol.Layout.topMargin,
                                             Math.min(wantH, (body.height - Theme.s(120)) * (!win.settingsOpen && tabs.currentIndex === 2 ? 0.36 : 0.46)))
                                    + 2 * padding
            RowLayout {
                id: screenRow
                anchors.fill: parent
                spacing: Theme.s(12)

                // preview with its header (as wide as the preview itself; any extra room goes
                // between the arrows and the controls)
                ColumnLayout {
                    id: previewCol
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: Math.max(Theme.s(160), (height - screenHead.implicitHeight - spacing)
                                                  * Math.max(0.5, ctrl.displayState.aspect || 16 / 9))
                    spacing: Theme.s(8)
                    RowLayout {
                        id: screenHead
                        Layout.fillWidth: true
                        spacing: Theme.s(8)
                        Icon { name: "book"; size: Theme.s(17); color: Theme.accent }
                        Text {
                            text: "ON SCREEN NOW"
                            font.family: Theme.font; font.pixelSize: Theme.s(12); font.weight: Font.DemiBold
                            font.letterSpacing: 0.4
                            color: Theme.accent
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            implicitHeight: Theme.s(24)
                            implicitWidth: refPill.implicitWidth + Theme.s(20)
                            Layout.maximumWidth: Theme.s(220)
                            radius: height / 2
                            color: ctrl.blank ? Theme.warningSoft : Theme.accentSoft
                            border.color: ctrl.blank ? "#FDE68A" : Theme.accentBorder
                            Text {
                                id: refPill
                                anchors.centerIn: parent
                                width: Math.min(implicitWidth, parent.width - Theme.s(16))
                                elide: Text.ElideRight
                                text: ctrl.blank ? "BLANK" : (ctrl.slideInfo.reference || "—").toUpperCase()
                                font.family: Theme.font; font.pixelSize: Theme.s(12); font.weight: Font.DemiBold
                                color: ctrl.blank ? Theme.warning : Theme.accent
                            }
                        }
                    }
                    SlidePreview {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: Theme.s(90)
                        controller: ctrl
                    }
                }

                // next / previous, stacked
                ColumnLayout {
                    id: navCol
                    Layout.alignment: Qt.AlignVCenter
                    Layout.topMargin: screenHead.implicitHeight
                    spacing: Theme.s(10)
                    AppButton {
                        iconName: "next"
                        implicitWidth: Theme.s(44); implicitHeight: Theme.s(44)
                        leftPadding: 0; rightPadding: 0
                        onClicked: ctrl.next()
                        ToolTip.visible: hovered; ToolTip.text: "Next verse (PgDn)"; ToolTip.delay: 500
                    }
                    AppButton {
                        iconName: "prev"
                        implicitWidth: Theme.s(44); implicitHeight: Theme.s(44)
                        leftPadding: 0; rightPadding: 0
                        onClicked: ctrl.prev()
                        ToolTip.visible: hovered; ToolTip.text: "Previous verse (PgUp)"; ToolTip.delay: 500
                    }
                }

                Item { Layout.fillWidth: true; Layout.preferredWidth: 0 }

                // display controls, one per row: evenly spaced from the top of the preview
                // to its bottom, labels left-aligned
                ColumnLayout {
                    id: ctlCol
                    Layout.fillWidth: false
                    Layout.preferredWidth: Theme.s(158)
                    Layout.maximumWidth: Theme.s(158)
                    Layout.fillHeight: true
                    Layout.topMargin: screenHead.implicitHeight + Theme.s(8)
                    spacing: Theme.s(15)
                    AppButton {
                        Layout.fillWidth: true
                        implicitHeight: Theme.s(30)
                        compact: true
                        alignLeft: true
                        font.pixelSize: Theme.s(12)
                        iconName: ctrl.displayState.visible ? "eye-off" : "eye"
                        text: ctrl.displayState.visible ? "Hide display" : "Show display"
                        onClicked: ctrl.setDisplayVisible(!ctrl.displayState.visible)
                        ToolTip.visible: hovered; ToolTip.text: "Show or hide the verse window (Ctrl+D)"; ToolTip.delay: 500
                    }
                    AppButton {
                        id: fsBtn
                        Layout.fillWidth: true
                        implicitHeight: Theme.s(30)
                        compact: true
                        alignLeft: true
                        font.pixelSize: Theme.s(12)
                        iconName: "monitor"
                        text: ctrl.displayState.fullscreen ? "Fullscreen ✓" : "Fullscreen on…"
                        rightPadding: Theme.s(26)
                        onClicked: fsMenu.popup(fsBtn, 0, fsBtn.height)
                        Icon { anchors.right: parent.right; anchors.rightMargin: Theme.s(9); anchors.verticalCenter: parent.verticalCenter
                               name: "chevron-down"; size: Theme.s(13); strokeWidth: 2.4; color: Theme.text }
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
                        Layout.fillWidth: true
                        implicitHeight: Theme.s(30)
                        compact: true
                        alignLeft: true
                        font.pixelSize: Theme.s(12)
                        iconName: "resize"
                        text: "Reset size"
                        onClicked: ctrl.resetDisplaySize()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "Reset to Default"
                    }
                    AppButton {
                        Layout.fillWidth: true
                        implicitHeight: Theme.s(30)
                        compact: true
                        alignLeft: true
                        font.pixelSize: Theme.s(12)
                        iconName: "square"
                        text: "Blank"
                        checkable: true
                        checked: ctrl.blank
                        onClicked: ctrl.toggleBlank()
                        ToolTip.visible: hovered; ToolTip.text: "Black screen (Ctrl+B)"; ToolTip.delay: 500
                    }
                    PillSwitch {
                        Layout.fillWidth: true
                        implicitHeight: Theme.s(30)
                        font.pixelSize: Theme.s(12)
                        text: "Always on top"; checked: ctrl.displayState.onTop; onToggled: ctrl.setOnTop(checked)
                    }
					Item { Layout.fillHeight: true } 
                }
            }
        }

        // ======== tabs
        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: Theme.s(200)
            padding: 0
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                // Settings header (replaces the tabs while Settings is open)
                RowLayout {
                    visible: win.settingsOpen
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.s(18)
                    Layout.rightMargin: Theme.s(14)
                    Layout.topMargin: Theme.s(6)
                    Layout.preferredHeight: Theme.s(48)
                    spacing: Theme.s(10)
                    Icon { name: "settings"; size: Theme.s(20); color: Theme.accent }
                    Text {
                        text: "Settings  ›  " + (win.settingsPage === "ai" ? "AI Mode Settings" : "Appearance")
                        font.family: Theme.font; font.pixelSize: Theme.s(16); font.weight: Font.DemiBold
                        color: Theme.accent
                    }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "Done"; compact: true; variant: "primary"; onClicked: win.settingsOpen = false }
                }
                TabBar {
                    id: tabs
                    objectName: "tabs"
                    visible: !win.settingsOpen
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.s(14)
                    Layout.rightMargin: Theme.s(14)
                    Layout.topMargin: Theme.s(6)
                    background: Item {}
                    Repeater {
                        model: ["Search", "History", "AI Mode"]
                        delegate: TabButton {
                            required property string modelData
                            required property int index
                            text: modelData
                            width: implicitWidth + Theme.s(20)
                            implicitHeight: Theme.s(38)
                            font.family: Theme.font; font.pixelSize: Theme.s(14)
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
                                    width: parent.width; height: 3; radius: 1.5
                                    color: tabs.currentIndex === index ? Theme.accent : "transparent"
                                }
                            }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; Layout.leftMargin: Theme.s(14); Layout.rightMargin: Theme.s(14); height: 1; color: Theme.border }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: Theme.s(14)
                    currentIndex: win.settingsOpen ? (win.settingsPage === "ai" ? 4 : 3) : tabs.currentIndex
                    SearchPage { id: searchPage }
                    HistoryPage {}
                    Loader {
                        id: aiLoader
                        active: tabs.currentIndex === 2 || item !== null
                        sourceComponent: AiPage { view: 0 }
                    }
                    AppearancePage {}
                    Loader {
                        id: aiSettingsLoader
                        active: (win.settingsOpen && win.settingsPage === "ai") || item !== null
                        sourceComponent: AiPage { objectName: "aiSettingsPage"; view: 1 }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ first run
    Card {
        visible: !ctrl.hasLibrary
        anchors.verticalCenter: parent.verticalCenter
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: sidebar.width / 2          // centered in the area beside the sidebar
        width: Math.min(Theme.s(520), parent.width - sidebar.width - 40)
        height: emptyCol.implicitHeight + 48
        padding: Theme.s(24)
        ColumnLayout {
            id: emptyCol
            width: parent.width
            spacing: Theme.s(12)
            Text { text: "Welcome to BibleQ-AI!"; font.pixelSize: Theme.fontTitle; font.weight: Font.Bold; color: Theme.text }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: Theme.s(4)
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: Theme.s(14)
                lineHeight: 1.15
                text: "No Bible versions/translations have been installed yet. To get started, import your Bible database file(s) (SQLite or DB3 format) to begin exploring Scripture."
            }
            AppButton { objectName: "welcomeImportButton"; Layout.topMargin: Theme.s(6); iconName: "import"; text: "Import Bible Version…"; variant: "primary"; onClicked: ctrl.importVersionFiles(); enabled: !ctrl.importState.running }
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
            spacing: Theme.s(6)
            RowLayout {
                spacing: Theme.s(12)
                Image { source: iconUrl; sourceSize: Qt.size(56, 56) }
                ColumnLayout {
                    spacing: 0
                    Text { text: ctrl.about.app; font.pixelSize: Theme.s(22); font.weight: Font.Bold; color: Theme.text }
                    Text { text: "Version " + ctrl.about.version; color: Theme.textMuted }
                }
            }
            Text { text: ctrl.about.description; color: Theme.text; Layout.topMargin: Theme.s(8); wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.maximumWidth: Theme.s(420) }
            Text { text: ctrl.about.author; font.weight: Font.DemiBold; color: Theme.text; Layout.topMargin: Theme.s(8) }
            Text { text: ctrl.about.locale; color: Theme.text }
            Text {
                text: "<a href='mailto:" + ctrl.about.email + "'>" + ctrl.about.email + "</a>"
                textFormat: Text.RichText
                linkColor: Theme.accent
                onLinkActivated: (link) => Qt.openUrlExternally(link)
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
            Text { text: ctrl.about.versions + " Bible versions installed"; color: Theme.textFaint; Layout.topMargin: Theme.s(8) }
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
            columnSpacing: Theme.s(24)
            rowSpacing: Theme.s(6)
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
        anchors.bottomMargin: Theme.s(24)
        width: toastText.implicitWidth + 32
        height: Theme.s(40)
        radius: Theme.s(20)
        color: "#1E293B"
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; text: toast.msg; color: "white"; font.pixelSize: Theme.fontSize }
        Timer { id: toastTimer; interval: 4000; onTriggered: toast.opacity = 0 }
    }
}
