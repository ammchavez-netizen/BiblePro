import QtQuick
import QtQuick.Shapes

// Soft blue background with flowing diagonal waves (sidebar).
Item {
    id: root
    clip: true
    readonly property real w: width
    readonly property real h: height

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#F6F9FF" }
            GradientStop { position: 0.45; color: "#EEF3FD" }
            GradientStop { position: 1.0; color: "#E2EBFB" }
        }
    }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        // 1) wide pale-blue sweep rising to the right
        ShapePath {
            strokeColor: "transparent"
            fillColor: Qt.rgba(196/255, 214/255, 248/255, 0.38)
            startX: 0; startY: root.h * 0.47
            PathCubic { x: root.w; y: root.h * 0.30
                        control1X: root.w * 0.30; control1Y: root.h * 0.45
                        control2X: root.w * 0.62; control2Y: root.h * 0.36 }
            PathLine { x: root.w; y: root.h }
            PathLine { x: 0; y: root.h }
        }
        // 2) bright highlight band just below it
        ShapePath {
            strokeColor: "transparent"
            fillColor: Qt.rgba(1, 1, 1, 0.55)
            startX: 0; startY: root.h * 0.53
            PathCubic { x: root.w; y: root.h * 0.37
                        control1X: root.w * 0.35; control1Y: root.h * 0.51
                        control2X: root.w * 0.66; control2Y: root.h * 0.43 }
            PathLine { x: root.w; y: root.h * 0.47 }
            PathCubic { x: 0; y: root.h * 0.63
                        control1X: root.w * 0.66; control1Y: root.h * 0.53
                        control2X: root.w * 0.35; control2Y: root.h * 0.61 }
        }
        // 3) deeper blue wave in the lower part
        ShapePath {
            strokeColor: "transparent"
            fillColor: Qt.rgba(176/255, 200/255, 244/255, 0.30)
            startX: 0; startY: root.h * 0.74
            PathCubic { x: root.w; y: root.h * 0.55
                        control1X: root.w * 0.32; control1Y: root.h * 0.70
                        control2X: root.w * 0.66; control2Y: root.h * 0.60 }
            PathLine { x: root.w; y: root.h }
            PathLine { x: 0; y: root.h }
        }
        // 4) thin light line following the lower wave
        ShapePath {
            strokeColor: Qt.rgba(1, 1, 1, 0.7)
            strokeWidth: 1.5
            fillColor: "transparent"
            startX: 0; startY: root.h * 0.80
            PathCubic { x: root.w; y: root.h * 0.62
                        control1X: root.w * 0.34; control1Y: root.h * 0.76
                        control2X: root.w * 0.68; control2Y: root.h * 0.67 }
        }
    }
}
