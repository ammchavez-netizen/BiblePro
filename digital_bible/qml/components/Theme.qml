pragma Singleton
import QtQuick

// One place for colors, sizes and fonts (light theme).
QtObject {
    readonly property color bg: "#F4F6FA"
    readonly property color surface: "#FFFFFF"
    readonly property color surfaceAlt: "#F8FAFC"
    readonly property color border: "#E2E8F0"
    readonly property color borderStrong: "#CBD5E1"
    readonly property color text: "#0F172A"
    readonly property color textMuted: "#64748B"
    readonly property color textFaint: "#94A3B8"
    readonly property color accent: "#2563EB"
    readonly property color accentHover: "#1D4ED8"
    readonly property color accentSoft: "#EFF4FF"
    readonly property color accentText: "#FFFFFF"
    readonly property color danger: "#DC2626"
    readonly property color dangerSoft: "#FEF2F2"
    readonly property color success: "#16A34A"
    readonly property color successSoft: "#F0FDF4"
    readonly property color warning: "#B45309"
    readonly property color warningSoft: "#FFFBEB"
    readonly property color gold: "#D4A017"

    readonly property int radius: 10
    readonly property int radiusSmall: 7
    readonly property int pad: 16
    readonly property int gap: 10
    readonly property int controlHeight: 36

    readonly property string font: Qt.platform.os === "windows" ? "Segoe UI" : "Inter"
    readonly property int fontSize: 13
    readonly property int fontSmall: 12
    readonly property int fontLarge: 16
    readonly property int fontTitle: 20
}
