import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// The AI Mode chat. Used in the AI Mode tab and in the pop-out chat window;
// both show the same conversation (it lives in aiCtrl).
Item {
    id: root
    property bool popout: false          // true inside the pop-out window
    signal popOutRequested()
    signal dockRequested()
    signal settingsRequested()
    readonly property var st: aiCtrl.indexStatus
    readonly property var prog: aiCtrl.progress
    readonly property var gen: aiCtrl.generation

    function focusInput() { input.forceActiveFocus() }

    component Small: Text {
        font.family: Theme.font; font.pixelSize: Theme.fontSmall
        color: Theme.textMuted
        wrapMode: Text.Wrap
    }
    component Body: Text {
        font.family: Theme.font; font.pixelSize: Theme.fontSize
        color: Theme.text
        wrapMode: Text.Wrap
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // ---- header line: answer source + pop-out
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                width: 8; height: 8; radius: 4
                color: root.gen.available && root.gen.enabled ? Theme.success : Theme.textFaint
            }
            Small {
                Layout.fillWidth: true
                elide: Text.ElideRight
                wrapMode: Text.NoWrap
                text: root.gen.available && root.gen.enabled
                      ? "AI answers: " + root.gen.model
                      : "AI answers off — showing Bible passages only"
            }
            AppButton {
                text: root.popout ? "Dock back" : "Pop out ⧉"
                compact: true
                variant: "ghost"
                onClicked: root.popout ? root.dockRequested() : root.popOutRequested()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: root.popout ? "Put the chat back into the AI Mode tab"
                                          : "Open the chat in its own window beside BiblePro"
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.st.state !== "ready" && !root.prog.running
            implicitHeight: bannerRow.implicitHeight + 16
            radius: 8
            color: Theme.warningSoft
            border.color: "#FDE68A"
            RowLayout {
                id: bannerRow
                anchors.fill: parent
                anchors.margins: 8
                Small {
                    Layout.fillWidth: true
                    color: Theme.warning
                    text: aiCtrl.packages.frozen && !aiCtrl.packages.ok
                          ? "BiblePro.exe searches by keywords only. For meaning-based search, start BiblePro with run.bat."
                          : !aiCtrl.packages.ok
                          ? "AI components are not installed, so only keyword search is available. Run:  pip install -r requirements-ai.txt"
                          : "The search index is " + root.st.state + ". Build it once (Settings) for meaning-based search — keyword search works meanwhile."
                }
                AppButton { visible: aiCtrl.packages.ok; text: "Build index"; compact: true; variant: "primary"; onClicked: aiCtrl.buildIndex() }
            }
        }

        ListView {
            id: chat
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 12
            model: aiCtrl.messages
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            onCountChanged: Qt.callLater(() => chat.positionViewAtEnd())
            delegate: Item {
                id: msg
                required property var modelData
                required property int index
                width: ListView.view.width - 10
                height: bubble.height
                readonly property bool isUser: modelData.role === "user"
                readonly property var allSources: modelData.sources || []
                readonly property var cited: modelData.cited || []
                property bool showAll: false
                // cited passages first (in citation order), then the rest
                readonly property var ordered: {
                    var out = [], seen = {}
                    for (var i = 0; i < cited.length; i++) {
                        var n = cited[i]
                        if (n >= 1 && n <= allSources.length) { out.push({ n: n, s: allSources[n - 1], cited: true }); seen[n] = true }
                    }
                    for (var j = 0; j < allSources.length; j++)
                        if (!seen[j + 1]) out.push({ n: j + 1, s: allSources[j], cited: false })
                    return out
                }
                readonly property int shownCount: showAll ? ordered.length
                                                 : (cited.length > 0 ? cited.length : Math.min(ordered.length, 5))

                Rectangle {
                    id: bubble
                    anchors.right: msg.isUser ? parent.right : undefined
                    width: msg.isUser ? Math.min(parent.width * 0.8, userText.implicitWidth + 28) : parent.width
                    height: msgCol.implicitHeight + 24
                    radius: 12
                    color: msg.isUser ? Theme.accent : Theme.surface
                    border.color: msg.isUser ? Theme.accent : Theme.border
                    ColumnLayout {
                        id: msgCol
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8
                        Text {
                            id: userText
                            visible: msg.isUser
                            Layout.fillWidth: true
                            text: msg.modelData.text
                            color: "white"
                            font.family: Theme.font; font.pixelSize: Theme.fontSize
                            wrapMode: Text.Wrap
                        }
                        RowLayout {
                            visible: !msg.isUser && msg.modelData.pending === true
                            BusyIndicator { implicitWidth: 22; implicitHeight: 22; running: parent.visible }
                            Small { text: root.gen.available && root.gen.enabled ? "Searching the Bibles and writing an answer…" : "Searching the Bibles…" }
                        }
                        Text {
                            visible: !msg.isUser && !msg.modelData.pending
                            Layout.fillWidth: true
                            text: msg.modelData.text || ""
                            textFormat: msg.modelData.error ? Text.PlainText : Text.MarkdownText
                            color: msg.modelData.error ? Theme.danger : Theme.text
                            linkColor: Theme.accent
                            font.family: Theme.font; font.pixelSize: Theme.fontSize + 1
                            lineHeight: 1.15
                            wrapMode: Text.Wrap
                            onLinkActivated: (link) => {
                                if (link.indexOf("cite:") === 0) {
                                    var s = msg.allSources[parseInt(link.substring(5)) - 1]
                                    if (s) aiCtrl.openVerse(s.key, s.code)
                                } else Qt.openUrlExternally(link)
                            }
                            HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
                        }
                        Small {
                            visible: !msg.isUser && !msg.modelData.pending && ((msg.modelData.language || "") !== "" || (msg.modelData.model || "") !== "")
                            color: Theme.textFaint
                            text: [msg.modelData.mode === "ai" ? "Written by " + msg.modelData.model + " from the passages below" : "",
                                   (msg.modelData.language || "") !== "" ? "Question language: " + msg.modelData.language : ""]
                                  .filter(x => x !== "").join("  ·  ")
                        }
                        Repeater {
                            model: msg.isUser ? [] : (msg.modelData.notes || [])
                            delegate: Small { required property var modelData; Layout.fillWidth: true; text: "⚠ " + modelData; color: Theme.warning }
                        }
                        // ---- sources
                        SectionLabel {
                            visible: !msg.isUser && msg.allSources.length > 0
                            text: msg.cited.length > 0 ? "Cited passages" : "Biblical references"
                            Layout.topMargin: 4
                        }
                        Repeater {
                            model: msg.isUser ? [] : msg.ordered.slice(0, msg.shownCount)
                            delegate: Rectangle {
                                id: src
                                required property var modelData
                                readonly property var s: modelData.s
                                Layout.fillWidth: true
                                implicitHeight: srcCol.implicitHeight + 16
                                radius: 8
                                color: Theme.surfaceAlt
                                border.color: src.modelData.cited ? "#C7D7FE" : Theme.border
                                ColumnLayout {
                                    id: srcCol
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 4
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        Text {
                                            text: "<a href='#'>" + src.s.reference + "</a>"
                                            textFormat: Text.RichText
                                            linkColor: Theme.accent
                                            font.family: Theme.font; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                                            onLinkActivated: aiCtrl.openVerse(src.s.key, src.s.code)
                                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                                        }
                                        Small { text: src.s.abbr + " · " + src.s.language; wrapMode: Text.NoWrap }
                                        Item { Layout.fillWidth: true }
                                        Small {
                                            text: (src.s.methods || []).join(" + ")
                                                  + (src.s.similarity !== null && src.s.similarity !== undefined
                                                     ? "  ·  " + src.s.similarity.toFixed(2) : "")
                                            color: Theme.textFaint
                                            wrapMode: Text.NoWrap
                                        }
                                        AppButton {
                                            text: "Compare"
                                            compact: true
                                            variant: "ghost"
                                            onClicked: compareDlg.openFor(src.s.key, src.s.reference)
                                        }
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "“" + src.s.text + "”"
                                        font.family: Theme.font; font.pixelSize: Theme.fontSize; font.italic: true
                                        color: "#334155"
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }
                        }
                        AppButton {
                            visible: !msg.isUser && msg.ordered.length > msg.shownCount || msg.showAll && msg.ordered.length > 5
                            compact: true
                            variant: "ghost"
                            text: msg.showAll ? "Show fewer passages"
                                              : "Show " + (msg.ordered.length - msg.shownCount) + " more passage"
                                                + (msg.ordered.length - msg.shownCount === 1 ? "" : "s")
                            onClicked: msg.showAll = !msg.showAll
                        }
                    }
                }
            }
            // empty state
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 520)
                visible: chat.count === 0
                spacing: 10
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Ask about the Bible"
                    font.family: Theme.font; font.pixelSize: Theme.fontLarge; font.weight: Font.DemiBold
                    color: Theme.text
                }
                Small {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: "Ask in any language. Answers are grounded in the Bible versions you index (Ang Dating Biblia and King James Version by default)."
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: ["What does the Bible say about forgiveness?", "What does Jesus teach about loving your enemies?",
                                "Explain Romans 8:28", "Ano ang sinasabi ng Bibliya tungkol sa pananampalataya?",
                                "Compare John 3:16"]
                        delegate: Chip { required property string modelData; text: modelData; onClicked: input.text = modelData }
                    }
                }
            }
        }

        // ---- input
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(110, Math.max(44, input.implicitHeight))
                TextArea {
                    id: input
                    placeholderText: "Ask a question about the Bible…   (Enter to send, Shift+Enter for a new line)"
                    wrapMode: TextArea.Wrap
                    font.family: Theme.font; font.pixelSize: Theme.fontSize
                    color: Theme.text
                    placeholderTextColor: Theme.textFaint
                    leftPadding: 12; rightPadding: 12; topPadding: 11; bottomPadding: 11
                    background: Rectangle {
                        radius: Theme.radiusSmall
                        color: Theme.surface
                        border.width: input.activeFocus ? 2 : 1
                        border.color: input.activeFocus ? Theme.accent : Theme.borderStrong
                    }
                    Keys.onPressed: (event) => {
                        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) {
                            root.send(); event.accepted = true
                        }
                    }
                }
            }
            AppButton { text: "Send"; variant: "primary"; implicitHeight: 44; enabled: !aiCtrl.busy && input.text.trim() !== ""; onClicked: root.send() }
            AppButton { text: "Clear"; implicitHeight: 44; enabled: !aiCtrl.busy && chat.count > 0; onClicked: aiCtrl.clearChat() }
        }
    }

    function send() {
        var q = input.text.trim()
        if (q === "" || aiCtrl.busy) return
        aiCtrl.ask(q)
        input.text = ""
    }

    Dialog {
        id: compareDlg
        property var rows: []
        property string ref: ""
        function openFor(key, ref) { compareDlg.ref = ref; compareDlg.rows = aiCtrl.compare(key); open() }
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(900, parent.width - 60)
        height: Math.min(640, parent.height - 60)
        modal: true
        title: compareDlg.ref + " — " + compareDlg.rows.length + " translations"
        standardButtons: Dialog.Close
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        ColumnLayout {
            anchors.fill: parent
            AppTextField { id: cmpFilter; Layout.fillWidth: true; placeholderText: "Filter by language or version (e.g. English, Spanish, KJV)" }
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                ScrollBar.vertical: ScrollBar {}
                model: compareDlg.rows.filter(r => { var q = cmpFilter.text.toLowerCase(); return !q || (r.abbr + " " + r.language).toLowerCase().indexOf(q) >= 0 })
                delegate: ColumnLayout {
                    required property var modelData
                    width: ListView.view.width
                    spacing: 1
                    Small { text: modelData.abbr + " · " + modelData.language + " · " + modelData.reference; color: Theme.accent; font.weight: Font.DemiBold }
                    Body { Layout.fillWidth: true; text: modelData.text }
                }
            }
        }
    }
}
