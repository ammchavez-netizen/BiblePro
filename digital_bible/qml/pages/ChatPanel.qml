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
        spacing: Theme.s(10)

        // ---- header line: answer source + pop-out
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.s(8)
            Rectangle {
                width: Theme.s(8); height: Theme.s(8); radius: Theme.s(4)
                color: root.gen.available && root.gen.enabled ? Theme.success : Theme.textFaint
            }
            Small {
                Layout.fillWidth: true
                elide: Text.ElideRight
                wrapMode: Text.NoWrap
                text: (root.gen.available && root.gen.enabled
                       ? "AI answers: " + root.gen.model
                       : "AI answers off — showing Bible passages only")
                      + (aiCtrl.warmup.state === "loading" ? "   ·   Loading the search engine…" : "")
            }
            AppButton {
                text: root.popout ? "Dock back" : "Pop out ⧉"
                compact: true
                variant: "soft"
                implicitHeight: Theme.s(30)
                font.weight: Font.DemiBold
                onClicked: root.popout ? root.dockRequested() : root.popOutRequested()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: root.popout ? "Put the chat back into the AI Mode tab"
                                          : "Open the chat in its own window beside BibleQ-AI"
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.st.state !== "ready" && !root.prog.running
            implicitHeight: bannerRow.implicitHeight + 16
            radius: Theme.s(8)
            color: Theme.warningSoft
            border.color: "#FDE68A"
            RowLayout {
                id: bannerRow
                anchors.fill: parent
                anchors.margins: Theme.s(8)
                Small {
                    Layout.fillWidth: true
                    color: Theme.warning
                    text: aiCtrl.packages.frozen && !aiCtrl.packages.ok
                          ? "BibleQ-AI.exe searches by keywords only. For meaning-based search, start BibleQ-AI with run.bat."
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
            spacing: Theme.s(12)
            model: aiCtrl.chatModel
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            // follow the answer as it is written, unless the user scrolled up to read
            property bool stick: true
            onMovementEnded: stick = atYEnd
            onCountChanged: { stick = true; Qt.callLater(() => chat.positionViewAtEnd()) }
            onContentHeightChanged: if (stick && aiCtrl.busy) Qt.callLater(() => chat.positionViewAtEnd())
            delegate: Item {
                id: msg
                required property var entry
                required property int index
                width: ListView.view.width - 10
                height: bubble.height
                readonly property bool isUser: entry.role === "user"
                readonly property var allSources: entry.sources || []
                readonly property var cited: entry.cited || []
                readonly property string phase: entry.phase || (entry.pending ? "searching" : "done")
                property bool showAll: false
                // Biblical references start collapsed when Gemini writes an answer (so the answer
                // is what you see), and open when there's no AI answer (the verses are the answer).
                property bool refsToggled: false
                property bool refsUserOpen: false
                readonly property bool refsOpen: refsToggled ? refsUserOpen : entry.mode !== "ai"
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
                    radius: Theme.s(12)
                    color: msg.isUser ? Theme.accent : Theme.surface
                    border.color: msg.isUser ? Theme.accent : Theme.border
                    ColumnLayout {
                        id: msgCol
                        anchors.fill: parent
                        anchors.margins: Theme.s(12)
                        spacing: Theme.s(8)
                        Text {
                            id: userText
                            visible: msg.isUser
                            Layout.fillWidth: true
                            text: msg.entry.text
                            color: "white"
                            font.family: Theme.font; font.pixelSize: Theme.fontSize
                            wrapMode: Text.Wrap
                        }
                        RowLayout {
                            visible: !msg.isUser && msg.phase === "searching"
                            BusyIndicator { implicitWidth: Theme.s(22); implicitHeight: Theme.s(22); running: parent.visible }
                            Small { text: aiCtrl.warmup.state === "loading" ? "Loading the search engine, then searching the Bibles…"
                                                                            : "Searching the Bibles…" }
                        }
                        Text {
                            visible: !msg.isUser && msg.phase !== "searching" && (msg.entry.text || "") !== ""
                            Layout.fillWidth: true
                            text: msg.entry.text || ""
                            textFormat: msg.entry.error ? Text.PlainText : Text.MarkdownText
                            color: msg.entry.error ? Theme.danger : Theme.text
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
                        // Gemini status while the answer is being written
                        RowLayout {
                            visible: !msg.isUser && msg.phase === "generating"
                            spacing: Theme.s(8)
                            BusyIndicator { implicitWidth: Theme.s(20); implicitHeight: Theme.s(20); running: parent.visible }
                            Small {
                                text: (msg.entry.text || "") === "" || msg.entry.stalled ? "Gemini is thinking…" : "Gemini is writing…"
                                color: Theme.accent
                                font.italic: true
                            }
                        }
                        Small {
                            visible: !msg.isUser && msg.phase === "done" && !msg.entry.error
                            Layout.fillWidth: true
                            color: Theme.textFaint
                            text: {
                                var e = msg.entry, t = e.timing || {}, parts = []
                                if (e.mode === "ai") parts.push("Written by " + e.model + " from the passages below")
                                if ((e.language || "") !== "") parts.push("Question language: " + e.language)
                                if (t.search !== undefined) parts.push("passages found in " + t.search + " s")
                                if (t.first !== undefined) parts.push("first words after " + t.first + " s")
                                if (t.total !== undefined) parts.push("done in " + t.total + " s")
                                return parts.join("  ·  ")
                            }
                        }
                        Repeater {
                            model: msg.isUser ? [] : (msg.entry.notes || [])
                            delegate: Small { required property var modelData; Layout.fillWidth: true; text: "⚠ " + modelData; color: Theme.warning }
                        }
                        // ---- sources
                        AppButton {
                            visible: !msg.isUser && msg.allSources.length > 0
                            Layout.topMargin: Theme.s(2)
                            compact: true
                            variant: "ghost"
                            text: (msg.refsOpen ? "▾  Hide " : "▸  Show ") + "Biblical references ("
                                  + (msg.cited.length > 0 ? msg.cited.length + " cited, " : "") + msg.allSources.length + " found)"
                            onClicked: { msg.refsUserOpen = !msg.refsOpen; msg.refsToggled = true }
                        }
                        Repeater {
                            model: msg.isUser || !msg.refsOpen ? [] : msg.ordered.slice(0, msg.shownCount)
                            delegate: Rectangle {
                                id: src
                                required property var modelData
                                readonly property var s: modelData.s
                                Layout.fillWidth: true
                                implicitHeight: srcCol.implicitHeight + 16
                                radius: Theme.s(8)
                                color: Theme.surfaceAlt
                                border.color: src.modelData.cited ? "#C7D7FE" : Theme.border
                                ColumnLayout {
                                    id: srcCol
                                    anchors.fill: parent
                                    anchors.margins: Theme.s(8)
                                    spacing: Theme.s(4)
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.s(8)
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
                            visible: !msg.isUser && msg.refsOpen && (msg.ordered.length > msg.shownCount || msg.showAll && msg.ordered.length > 5)
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
                spacing: Theme.s(10)
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
                // example questions, centered under the heading
                Repeater {
                    model: ["Mga talata tungkol sa mabubuting gawa", "What are the commandments of our lord Jesus?"]
                    delegate: Chip {
                        required property string modelData
                        Layout.alignment: Qt.AlignHCenter
                        text: modelData
                        onClicked: input.text = modelData
                    }
                }
            }
        }

        // ---- input
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.s(8)
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
                    leftPadding: Theme.s(12); rightPadding: Theme.s(12); topPadding: Theme.s(11); bottomPadding: Theme.s(11)
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
            AppButton { text: "Send"; variant: "primary"; implicitHeight: Theme.s(44); enabled: !aiCtrl.busy && input.text.trim() !== ""; onClicked: root.send() }
            AppButton { text: "Clear"; implicitHeight: Theme.s(44); enabled: !aiCtrl.busy && chat.count > 0; onClicked: aiCtrl.clearChat() }
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
                spacing: Theme.s(6)
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
