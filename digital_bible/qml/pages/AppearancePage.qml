import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// How the verse looks on the display.
ScrollView {
    id: root
    readonly property var st: ctrl.style
    clip: true
    contentWidth: availableWidth

    component Label_: Text {
        font.family: Theme.font; font.pixelSize: Theme.fontSize
        color: Theme.text
    }

    ColumnLayout {
        width: root.availableWidth
        spacing: 18

        // ---- text
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            SectionLabel { text: "Text" }
            GridLayout {
                Layout.fillWidth: true
                columns: 4
                columnSpacing: 12
                rowSpacing: 10
                Label_ { text: "Font" }
                AppComboBox {
                    id: fontBox
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    model: ctrl.fonts
                    currentIndex: Math.max(0, ctrl.fonts.indexOf(root.st.font_family))
                    onActivated: ctrl.setStyleValue("font_family", currentText)
                }
                AppSwitch { text: "Bold"; checked: root.st.bold; onToggled: ctrl.setStyleValue("bold", checked) }

                Label_ { text: "Max size" }
                SpinBox {
                    from: 30; to: 300; stepSize: 5; editable: true
                    value: root.st.max_size
                    onValueModified: ctrl.setStyleValue("max_size", value)
                    font.family: Theme.font
                    ToolTip.visible: hovered; ToolTip.delay: 600
                    ToolTip.text: "Largest text size (px at 1080p). Long verses shrink to fit."
                }
                Label_ { text: "Margin %" }
                SpinBox {
                    from: 0; to: 25
                    value: root.st.margin
                    onValueModified: ctrl.setStyleValue("margin", value)
                    font.family: Theme.font
                }
                Label_ { text: "Align" }
                AppComboBox {
                    Layout.preferredWidth: 140
                    model: ["Center", "Left"]
                    currentIndex: root.st.align === "left" ? 1 : 0
                    onActivated: ctrl.setStyleValue("align", currentIndex === 1 ? "left" : "center")
                }
                AppSwitch { text: "Shadow"; checked: root.st.shadow; onToggled: ctrl.setStyleValue("shadow", checked) }
                Item { width: 1 }
            }
        }

        // ---- colors + label
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            SectionLabel { text: "Colors and top-left label" }
            Flow {
                Layout.fillWidth: true
                spacing: 14
                Row { spacing: 8
                    Label_ { text: "Verse"; anchors.verticalCenter: parent.verticalCenter }
                    ColorSwatch { swatch: root.st.text_color; onClicked: ctrl.pickColor("text_color") } }
                Row { spacing: 8
                    Label_ { text: "Version name"; anchors.verticalCenter: parent.verticalCenter }
                    ColorSwatch { swatch: root.st.ref_color; onClicked: ctrl.pickColor("ref_color") } }
                AppSwitch { text: "Show reference"; checked: root.st.show_reference; onToggled: ctrl.setStyleValue("show_reference", checked) }
                AppSwitch { text: "Show version name"; checked: root.st.show_version; onToggled: ctrl.setStyleValue("show_version", checked) }
            }
        }

        // ---- background
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            SectionLabel { text: "Background" }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                AppComboBox {
                    Layout.preferredWidth: 150
                    model: ["Image", "Solid color"]
                    currentIndex: root.st.bg_mode === "color" ? 1 : 0
                    onActivated: ctrl.setStyleValue("bg_mode", currentIndex === 1 ? "color" : "image")
                }
                Label_ { text: "Color" }
                ColorSwatch { swatch: root.st.bg_color; onClicked: ctrl.pickColor("bg_color") }
                Label_ { text: "Darken" }
                Slider {
                    Layout.fillWidth: true
                    from: 0; to: 85; stepSize: 1
                    value: root.st.dim
                    onMoved: ctrl.setStyleValue("dim", Math.round(value))
                }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Repeater {
                    model: ctrl.backgrounds
                    delegate: AbstractButton {
                        id: thumb
                        required property var modelData
                        width: 132; height: 74
                        hoverEnabled: true
                        onClicked: { ctrl.setStyleValue("bg_mode", "image"); ctrl.setStyleValue("background", modelData.name) }
                        ToolTip.visible: hovered; ToolTip.text: modelData.label; ToolTip.delay: 500
                        background: Rectangle {
                            radius: 8
                            color: Theme.surfaceAlt
                            border.width: (root.st.background === thumb.modelData.name && root.st.bg_mode === "image") ? 3 : 1
                            border.color: border.width > 1 ? Theme.accent : (thumb.hovered ? Theme.borderStrong : Theme.border)
                            clip: true
                            Image {
                                anchors.fill: parent
                                anchors.margins: parent.border.width
                                source: thumb.modelData.url
                                fillMode: Image.PreserveAspectCrop
                                sourceSize.width: 264
                                asynchronous: true
                            }
                        }
                    }
                }
                AppButton { text: "+ Add image…"; height: 74; onClicked: ctrl.addBackground() }
            }
        }
        Item { Layout.preferredHeight: 6 }
    }
}
