import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// AI Mode: Bible research chat + settings (index, embedding model, search, API key).
Item {
    id: root
    objectName: "aiPage"
    property int view: 0                       // 0 = chat, 1 = settings
    readonly property var st: aiCtrl.indexStatus
    readonly property var prog: aiCtrl.progress

    Connections {
        target: aiCtrl
        function onNotice(msg) { noticeBar.show(msg) }
    }

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

        // ---------- top bar: view switch + index state
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                implicitWidth: seg.implicitWidth + 6
                implicitHeight: 34
                radius: 8
                color: Theme.surfaceAlt
                border.color: Theme.border
                Row {
                    id: seg
                    anchors.centerIn: parent
                    spacing: 2
                    Repeater {
                        model: ["Chat", "Settings"]
                        delegate: AbstractButton {
                            required property string modelData
                            required property int index
                            width: 92; height: 28
                            onClicked: { root.view = index; if (index === 1) aiCtrl.refreshLog() }
                            background: Rectangle { radius: 6; color: root.view === index ? Theme.surface : "transparent"
                                border.color: root.view === index ? Theme.border : "transparent" }
                            contentItem: Text { text: modelData; font.family: Theme.font; font.pixelSize: Theme.fontSize
                                font.weight: root.view === index ? Font.DemiBold : Font.Normal
                                color: root.view === index ? Theme.text : Theme.textMuted
                                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: 11
                implicitHeight: 22
                implicitWidth: stateText.implicitWidth + 18
                color: root.st.state === "ready" ? Theme.successSoft : root.st.state === "error" ? Theme.dangerSoft : Theme.warningSoft
                Text {
                    id: stateText
                    anchors.centerIn: parent
                    text: "Index: " + (root.st.state || "…") + (root.st.selected_versions ? "  ·  " + root.st.selected_versions.join(", ") : "")
                    font.family: Theme.font; font.pixelSize: 11; font.weight: Font.DemiBold
                    color: root.st.state === "ready" ? Theme.success : root.st.state === "error" ? Theme.danger : Theme.warning
                }
            }
        }

        // ---------- progress strip (visible while indexing / downloading)
        Rectangle {
            Layout.fillWidth: true
            visible: root.prog.running
            implicitHeight: progCol.implicitHeight + 16
            radius: 8
            color: Theme.accentSoft
            border.color: "#C7D7FE"
            ColumnLayout {
                id: progCol
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    BusyIndicator { running: root.prog.running; implicitWidth: 22; implicitHeight: 22 }
                    Body { Layout.fillWidth: true; text: root.prog.message; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                    AppButton { text: "Cancel"; compact: true; onClicked: aiCtrl.cancelIndex() }
                }
                ProgressBar {
                    Layout.fillWidth: true
                    from: 0; to: 100
                    value: root.prog.percent
                    indeterminate: root.prog.total === 0
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.view

            // =========================================================== CHAT
            Item {
                ChatPanel {
                    id: chatPanel
                    anchors.fill: parent
                    visible: !aiCtrl.chatPoppedOut
                    onPopOutRequested: aiCtrl.setChatPoppedOut(true)
                }
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 40, 440)
                    visible: aiCtrl.chatPoppedOut
                    spacing: 12
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "The chat is open in its own window"
                        font.family: Theme.font; font.pixelSize: Theme.fontLarge; font.weight: Font.DemiBold
                        color: Theme.text
                    }
                    Small {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: "It sits to the right of BiblePro and follows it when you move or resize this window."
                    }
                    AppButton {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Bring the chat back here"
                        onClicked: aiCtrl.setChatPoppedOut(false)
                    }
                }
            }

            // =========================================================== SETTINGS
            ScrollView {
                id: settingsView
                objectName: "aiSettingsView"
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: settingsView.availableWidth
                    spacing: 22

                    // ---- missing packages
                    Rectangle {
                        Layout.fillWidth: true
                        visible: aiCtrl.packages.missing.length > 0
                        implicitHeight: pkgCol.implicitHeight + 20
                        radius: 8
                        color: Theme.warningSoft
                        border.color: "#FDE68A"
                        ColumnLayout {
                            id: pkgCol
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 4
                            Body { text: aiCtrl.packages.frozen ? "BiblePro.exe searches by keywords only"
                                                                : "Some AI components are not installed: " + aiCtrl.packages.missing.join(", ")
                                   font.weight: Font.DemiBold; color: Theme.warning; Layout.fillWidth: true }
                            Small { Layout.fillWidth: true
                                    text: aiCtrl.packages.frozen
                                          ? "To keep the .exe small, it doesn't include the meaning-based search (PyTorch, bge-m3, ChromaDB). Gemini answers still work. For meaning-based search, start BiblePro with run.bat."
                                          : "In the BiblePro folder run:   .venv\\Scripts\\python -m pip install -r requirements-ai.txt   then restart BiblePro." }
                        }
                    }

                    // ---- index status
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        SectionLabel { text: "Bible index" }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: width > 520 ? 4 : 2
                            columnSpacing: 10
                            rowSpacing: 10
                            Repeater {
                                model: [
                                    ["Databases found", root.st.databases_found],
                                    ["Indexed", (root.st.databases_indexed || 0) + " / " + (root.st.translations || 0)],
                                    ["With errors", root.st.databases_with_errors],
                                    ["Languages", root.st.languages],
                                    ["Verses indexed", (root.st.verses_indexed || 0).toLocaleString(Qt.locale(), "f", 0)],
                                    ["Embeddings", (root.st.embeddings || 0).toLocaleString(Qt.locale(), "f", 0)],
                                    ["Last indexed", root.st.last_indexed_text],
                                    ["Status", root.st.state]
                                ]
                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    implicitHeight: 58
                                    radius: 8
                                    color: Theme.surfaceAlt
                                    border.color: Theme.border
                                    Column {
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: 12
                                        spacing: 2
                                        Small { text: modelData[0] }
                                        Text { text: String(modelData[1] === undefined ? "–" : modelData[1]); font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold; color: Theme.text }
                                    }
                                }
                            }
                        }
                        Small { Layout.fillWidth: true; text: "Embedding model: " + (root.st.embedding_model || "") }
                        Small {
                            Layout.fillWidth: true
                            visible: !root.prog.running && root.prog.message !== ""
                            text: root.prog.message + (root.prog.errors && root.prog.errors.length ? "  —  " + root.prog.errors.join("; ") : "")
                            color: root.prog.stage === "error" ? Theme.danger : Theme.textMuted
                        }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 8
                            AppButton { text: "Scan Bible Databases"; enabled: !root.prog.running; onClicked: aiCtrl.scanDatabases() }
                            AppButton { text: "Build Index"; variant: "primary"; enabled: !root.prog.running; onClicked: aiCtrl.buildIndex() }
                            AppButton { text: "Refresh Index"; enabled: !root.prog.running; onClicked: aiCtrl.buildIndex()
                                ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "Only processes Bibles that are new or changed" }
                            AppButton { text: "Rebuild Index…"; variant: "danger"; enabled: !root.prog.running; onClicked: rebuildDlg.open() }
                            AppButton { text: "View Indexing Logs"; onClicked: { aiCtrl.refreshLog(); logDlg.open() } }
                            AppButton { text: "View Database Details"; onClicked: { aiCtrl.refreshLog(); detailsDlg.open() } }
                            AppButton { text: "Back Up Index"; variant: "ghost"; enabled: !root.prog.running; onClicked: aiCtrl.backupIndex() }
                        }
                    }

                    // ---- which Bibles
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        SectionLabel { text: "Bibles used by AI Mode" }
                        Small { Layout.fillWidth: true; text: "Checked versions are indexed for AI search. To add another version, type its name below or click Show all. Comparing a verse still works across all versions." }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            AppTextField { id: vFilter; Layout.fillWidth: true; placeholderText: "Find a version to add (e.g. NIV, Spanish)…" }
                            AppButton { id: vShowAll; text: checked ? "Show checked only" : "Show all"; checkable: true; compact: true }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(44, Math.min(220, vList.contentHeight + 8))
                            radius: 8
                            color: Theme.surface
                            border.color: Theme.border
                            ListView {
                                id: vList
                                anchors.fill: parent
                                anchors.margins: 4
                                clip: true
                                ScrollBar.vertical: ScrollBar {}
                                // only checked versions, unless searching or "Show all"
                                model: aiCtrl.indexVersions.filter(v => {
                                    var q = vFilter.text.trim().toLowerCase()
                                    if (q) return (v.abbr + " " + v.name + " " + v.language).toLowerCase().indexOf(q) >= 0
                                    return vShowAll.checked || v.selected
                                }).sort((a, b) => (b.selected - a.selected))
                                delegate: CheckBox {
                                    required property var modelData
                                    width: ListView.view.width
                                    checked: modelData.selected
                                    text: modelData.abbr + "  —  " + modelData.name + "  (" + modelData.language + ")"
                                    font.family: Theme.font; font.pixelSize: Theme.fontSize
                                    onToggled: aiCtrl.setIndexedVersion(modelData.code, checked)
                                }
                                Small {
                                    anchors.centerIn: parent
                                    visible: vList.count === 0
                                    text: vFilter.text.trim() ? "No version matches “" + vFilter.text.trim() + "”." : "No versions selected."
                                }
                            }
                        }
                    }

                    // ---- embedding model
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        SectionLabel { text: "Embedding model (runs locally)" }
                        Small { Layout.fillWidth: true; text: "Turns verses and questions into vectors for meaning-based search. Runs on this computer — no API costs." }
                        Repeater {
                            model: aiCtrl.embedding.models
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: embRow.implicitHeight + 20
                                radius: 8
                                color: modelData.current ? Theme.accentSoft : Theme.surface
                                border.color: modelData.current ? "#C7D7FE" : Theme.border
                                RowLayout {
                                    id: embRow
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 10
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 1
                                        Body { Layout.fillWidth: true; text: modelData.name + (modelData.current ? "   (in use)" : ""); font.weight: Font.DemiBold }
                                        Small { Layout.fillWidth: true; text: modelData.id + " · " + modelData.dim + " dimensions · ~" + modelData.gb + " GB · "
                                                      + (modelData.downloaded ? "downloaded" : "not downloaded") }
                                    }
                                    AppButton { visible: !modelData.downloaded; text: "Download"; compact: true; enabled: !root.prog.running
                                        onClicked: aiCtrl.downloadModel(modelData.id) }
                                    AppButton { visible: !modelData.current; text: "Use this model"; compact: true
                                        onClicked: { switchDlg.modelId = modelData.id; switchDlg.open() } }
                                }
                            }
                        }
                    }

                    // ---- retrieval
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        SectionLabel { text: "Search tuning" }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 3
                            columnSpacing: 12
                            Body { text: "Verses per answer" }
                            SpinBox { from: 3; to: 40; value: aiCtrl.retrieval.final_k; onValueModified: aiCtrl.setRetrieval("final_k", value) }
                            Item { Layout.fillWidth: true }
                            Body { text: "Minimum similarity" }
                            Slider { id: simSlider; Layout.fillWidth: true; from: 0.1; to: 0.8; stepSize: 0.05
                                value: aiCtrl.retrieval.min_similarity; onMoved: aiCtrl.setRetrieval("min_similarity", value) }
                            Small { text: simSlider.value.toFixed(2) }
                            Body { text: "Prefer question's language" }
                            Slider { id: langSlider; Layout.fillWidth: true; from: 0; to: 1; stepSize: 0.05
                                value: aiCtrl.retrieval.language_boost; onMoved: aiCtrl.setRetrieval("language_boost", value) }
                            Small { text: "+" + Math.round(langSlider.value * 100) + "%" }
                        }
                    }

                    // ---- generative AI + API key (locked against accidental changes)
                    ColumnLayout {
                        id: geminiSec
                        objectName: "geminiSection"
                        Layout.fillWidth: true
                        spacing: 10
                        property bool unlocked: false
                        readonly property var g: aiCtrl.generation
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            SectionLabel { text: "AI answers — Google Gemini"; Layout.fillWidth: true }
                            Text {
                                text: geminiSec.unlocked ? "🔓 Editing" : "🔒 Locked"
                                font.family: Theme.font; font.pixelSize: Theme.fontSmall; font.weight: Font.DemiBold
                                color: geminiSec.unlocked ? Theme.warning : Theme.textMuted
                            }
                            AppButton {
                                text: geminiSec.unlocked ? "Lock" : "Unlock to edit"
                                compact: true
                                variant: geminiSec.unlocked ? "primary" : "secondary"
                                onClicked: {
                                    geminiSec.unlocked = !geminiSec.unlocked
                                    if (!geminiSec.unlocked) { keyField.text = ""; showKey.checked = false }
                                }
                                ToolTip.visible: hovered; ToolTip.delay: 500
                                ToolTip.text: "The API key and model can only be changed while this section is unlocked"
                            }
                        }
                        Small { Layout.fillWidth: true; text: geminiSec.g.note }

                        // status pill
                        RowLayout {
                            spacing: 8
                            Rectangle {
                                radius: 11
                                implicitHeight: 22
                                implicitWidth: pillText.implicitWidth + 18
                                color: geminiSec.g.available ? Theme.successSoft : Theme.warningSoft
                                Text {
                                    id: pillText
                                    anchors.centerIn: parent
                                    text: geminiSec.g.available ? (geminiSec.g.enabled ? "Ready" : "Ready · answers turned off")
                                                                : !aiCtrl.apiKey.set ? "No API key" : "Not available"
                                    font.family: Theme.font; font.pixelSize: 11; font.weight: Font.DemiBold
                                    color: geminiSec.g.available ? Theme.success : Theme.warning
                                }
                            }
                            AppSwitch {
                                text: "Write answers with Gemini"
                                checked: geminiSec.g.enabled
                                enabled: geminiSec.unlocked
                                onToggled: aiCtrl.setAnswersEnabled(checked)
                            }
                        }

                        // model
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 8
                            Body { text: "Model" }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                AppComboBox {
                                    id: modelBox
                                    Layout.fillWidth: true
                                    enabled: geminiSec.unlocked
                                    model: geminiSec.g.models
                                    textRole: "id"
                                    currentIndex: Math.max(0, geminiSec.g.models.findIndex(m => m.id === geminiSec.g.model))
                                    onActivated: (i) => aiCtrl.setModel(geminiSec.g.models[i].id)
                                }
                                AppButton {
                                    text: geminiSec.g.busy === "scan" ? "Scanning…" : "Scan Available Models"
                                    compact: true
                                    enabled: aiCtrl.apiKey.set && geminiSec.g.busy === ""
                                    onClicked: aiCtrl.scanModels()
                                }
                            }
                            Item { width: 1; height: 1 }
                            Small {
                                Layout.fillWidth: true
                                color: Theme.textFaint
                                text: {
                                    var m = geminiSec.g.models[modelBox.currentIndex]
                                    var parts = []
                                    if (m && m.name && m.name !== m.id) parts.push(m.name)
                                    if (m && m.input) parts.push(Math.round(m.input / 1000) + "K input tokens")
                                    parts.push(geminiSec.g.scanned ? "list updated " + geminiSec.g.scanned : "list not scanned yet")
                                    return parts.join(" · ")
                                }
                            }
                        }

                        // API key
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Body { text: "API key" }
                            AppTextField {
                                id: keyField
                                Layout.fillWidth: true
                                echoMode: showKey.checked ? TextInput.Normal : TextInput.Password
                                placeholderText: aiCtrl.apiKey.set ? "Saved: " + aiCtrl.apiKey.masked + (geminiSec.unlocked ? "  (type a new key to replace it)" : "")
                                                                   : (geminiSec.unlocked ? "Paste your Gemini API key" : "Unlock to add an API key")
                                enabled: aiCtrl.apiKey.available && geminiSec.unlocked
                            }
                            AppButton { id: showKey; text: checked ? "Hide" : "Show"; checkable: true; compact: true
                                enabled: geminiSec.unlocked
                                onToggled: if (checked && keyField.text === "") keyField.text = aiCtrl.revealApiKey() }
                            AppButton { text: "Save"; variant: "primary"; compact: true
                                enabled: geminiSec.unlocked && keyField.text.trim() !== ""
                                onClicked: { aiCtrl.saveApiKey(keyField.text); keyField.text = ""; showKey.checked = false } }
                            AppButton { text: "Remove…"; variant: "danger"; compact: true
                                enabled: geminiSec.unlocked && aiCtrl.apiKey.set
                                onClicked: clearKeyDlg.open() }
                        }
                        Small { Layout.fillWidth: true
                            text: aiCtrl.apiKey.available ? "Keys are stored in Windows Credential Manager, never in BiblePro's files. Get a key at aistudio.google.com."
                                                          : "Secure key storage is not available (install the AI components)." }

                        // test
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            AppButton {
                                text: geminiSec.g.busy === "test" ? "Testing…" : "Test Connection"
                                enabled: aiCtrl.apiKey.set && geminiSec.g.busy === ""
                                onClicked: aiCtrl.testConnection()
                            }
                            BusyIndicator { visible: geminiSec.g.busy !== ""; running: visible; implicitWidth: 24; implicitHeight: 24 }
                            Small {
                                Layout.fillWidth: true
                                visible: geminiSec.g.result && geminiSec.g.result.message !== undefined
                                text: geminiSec.g.result ? (geminiSec.g.result.ok ? "✓ " : "✕ ") + (geminiSec.g.result.message || "") : ""
                                color: geminiSec.g.result && geminiSec.g.result.ok ? Theme.success : Theme.danger
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 8 }
                }
            }
        }
    }

    // ---------- notice bar
    Rectangle {
        id: noticeBar
        property string msg: ""
        function show(m) { msg = m; opacity = 1; noticeTimer.restart() }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 64
        width: Math.min(parent.width - 20, noticeText.implicitWidth + 32)
        height: noticeText.implicitHeight + 18
        radius: 10
        color: "#1E293B"
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: noticeText; anchors.centerIn: parent; width: Math.min(implicitWidth, root.width - 52); text: noticeBar.msg; color: "white"; wrapMode: Text.Wrap; font.family: Theme.font; font.pixelSize: Theme.fontSmall }
        Timer { id: noticeTimer; interval: 5000; onTriggered: noticeBar.opacity = 0 }
    }

    // ---------- dialogs
    Dialog {
        id: rebuildDlg
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: "Rebuild the index?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        Body { width: 380; text: "This deletes the existing vectors and embeds every selected Bible again. It can take a while. Your Bible files are not touched." }
        onAccepted: aiCtrl.rebuildIndex()
    }
    Dialog {
        id: switchDlg
        property string modelId: ""
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: "Change embedding model?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        Body { width: 400; text: "Vectors from different models can't be mixed, so the index must be built again for “" + switchDlg.modelId + "”. The current model's index is kept in case you switch back." }
        onAccepted: aiCtrl.setEmbeddingModel(modelId)
    }
    Dialog {
        id: logDlg
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(900, parent.width - 60)
        height: Math.min(600, parent.height - 60)
        modal: true
        title: "Indexing log"
        standardButtons: Dialog.Close
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        ScrollView {
            anchors.fill: parent
            TextArea { readOnly: true; text: aiCtrl.indexLog; font.family: "Consolas"; font.pixelSize: 12; wrapMode: TextArea.NoWrap }
        }
    }
    Dialog {
        id: detailsDlg
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(900, parent.width - 60)
        height: Math.min(600, parent.height - 60)
        modal: true
        title: "Bible databases"
        standardButtons: Dialog.Close
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        ListView {
            anchors.fill: parent
            clip: true
            ScrollBar.vertical: ScrollBar {}
            model: aiCtrl.databaseDetails
            delegate: RowLayout {
                required property var modelData
                width: ListView.view.width
                spacing: 10
                Small { text: modelData.file; Layout.preferredWidth: 90; wrapMode: Text.NoWrap }
                Small { text: modelData.abbr; Layout.preferredWidth: 80; color: Theme.accent; wrapMode: Text.NoWrap }
                Small { text: modelData.translation; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap; color: Theme.text }
                Small { text: modelData.language + " (" + modelData.lang_code + ")"; Layout.preferredWidth: 140; wrapMode: Text.NoWrap }
                Small { text: modelData.error ? "error: " + modelData.error
                              : modelData.indexed ? "indexed · " + modelData.verses + " verses"
                              : modelData.selected ? "selected, not indexed" : "—"
                        color: modelData.error ? Theme.danger : modelData.indexed ? Theme.success : Theme.textMuted
                        Layout.preferredWidth: 170; wrapMode: Text.NoWrap }
            }
        }
    }
    Dialog {
        id: clearKeyDlg
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: "Remove the Gemini API key?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        background: Rectangle { radius: Theme.radius; color: Theme.surface; border.color: Theme.border }
        Body { width: 380; text: "The key will be deleted from Windows Credential Manager. AI Mode will show Bible passages only until you add a key again." }
        onAccepted: aiCtrl.clearApiKey()
    }
}
