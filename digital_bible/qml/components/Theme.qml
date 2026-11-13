pragma Singleton
import QtQuick

// One place for colors, sizes and fonts (light theme).
QtObject {
    // Window-size scale (set by the main window): every size below follows it.
    property real scale: 1.0
    function s(v) { return Math.round(v * scale) }

    readonly property color bg: "#EEF3FB"
    readonly property color bgTop: "#E8EFFB"         // window background gradient
    readonly property color bgBottom: "#F5F8FD"
    readonly property color sidebar: "#F7F9FE"
    readonly property color surface: "#FFFFFF"
    readonly property color surfaceAlt: "#F8FAFC"
    readonly property color border: "#E1E7F2"
    readonly property color borderStrong: "#CBD5E1"
    readonly property color text: "#111A33"
    readonly property color navy: "#1B2540"
    readonly property color textMuted: "#56627D"
    readonly property color textFaint: "#94A3B8"
    readonly property color accent: "#1463F3"
    readonly property color accentHover: "#0F54D6"
    readonly property color accentSoft: "#EAF1FF"
    readonly property color accentBorder: "#C9DAFD"
    readonly property color accentText: "#FFFFFF"
    readonly property color danger: "#DC2626"
    readonly property color dangerSoft: "#FEF2F2"
    readonly property color success: "#16A34A"
    readonly property color successSoft: "#F0FDF4"
    readonly property color warning: "#B45309"
    readonly property color warningSoft: "#FFFBEB"
    readonly property color gold: "#D4A017"

    readonly property int radius: s(14)
    readonly property int radiusSmall: s(9)
    readonly property int pad: s(14)
    readonly property int gap: s(9)
    readonly property int controlHeight: s(34)

    readonly property string font: Qt.platform.os === "windows" ? "Segoe UI" : "Inter"
    readonly property int fontSize: s(13)
    readonly property int fontSmall: s(11)
    readonly property int fontLarge: s(15)
    readonly property int fontTitle: s(19)
}
