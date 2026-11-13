import QtQuick
import QtQuick.Shapes

// Line icons drawn as vector paths (24x24 grid), so they stay sharp and take any color.
Item {
    id: root
    property string name: ""
    property color color: Theme.navy
    property real size: Theme.s(20)
    property real strokeWidth: 2
    implicitWidth: size
    implicitHeight: size

    readonly property var paths: ({
        "search": "M11 3a8 8 0 1 0 0 16a8 8 0 1 0 0-16z M21 21l-4.35-4.35",
        "history": "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M12 6.5v5.5l3.5 2",
        "palette": "M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.84-.44-1.13-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.55-2.5 5.55-5.55C21.97 6.01 17.46 2 12 2z M7.5 11.5a.6.6 0 1 0 0 .01 M10 7.5a.6.6 0 1 0 0 .01 M14.5 7a.6.6 0 1 0 0 .01 M17.5 10.5a.6.6 0 1 0 0 .01",
        "sparkle": "M12 1.5C12.6 7.6 16.4 11.4 22.5 12C16.4 12.6 12.6 16.4 12 22.5C11.4 16.4 7.6 12.6 1.5 12C7.6 11.4 11.4 7.6 12 1.5Z",
        "settings": "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z",
        "info": "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M12 16v-4.5 M12 8h.01",
        "book": "M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z",
        "chevron-left": "M15 18l-6-6 6-6",
        "chevron-right": "M9 18l6-6-6-6",
        "chevron-down": "M6 9l6 6 6-6",
        "import": "M12 3v12 M7 10l5 5 5-5 M5 21h14",
        "folder": "M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z",
        "keyboard": "M3 6h18v12H3z M7 10h.01 M11 10h.01 M15 10h.01 M7 14h10",
        "next": "M7 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z",
        "prev": "M17 4.5v15a1 1 0 0 1-1.5.86L3 12.86a1 1 0 0 1 0-1.72l12.5-7.5A1 1 0 0 1 17 4.5z",
        "eye-off": "M3 3l18 18 M10.6 5.1A9.8 9.8 0 0 1 12 5c5 0 9 4.5 10 7a12.7 12.7 0 0 1-2.9 4 M6.6 6.6C4.5 8 3 10.1 2 12c1 2.5 5 7 10 7a9.6 9.6 0 0 0 5.4-1.6 M9.9 9.9a3 3 0 0 0 4.2 4.2",
        "eye": "M2 12c1-2.5 5-7 10-7s9 4.5 10 7c-1 2.5-5 7-10 7S3 14.5 2 12z M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z",
        "monitor": "M3 4h18v12H3z M8 20h8 M12 16v4",
        "resize": "M15 3h6v6 M9 21H3v-6 M21 3l-7 7 M3 21l7-7",
        "square": "M5 5h14v14H5z"
    })
    readonly property var filledIcons: ({ "sparkle": true, "next": true, "prev": true })

    Shape {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.filledIcons[root.name] ? "transparent" : root.color
            fillColor: root.filledIcons[root.name] ? root.color : "transparent"
            strokeWidth: root.strokeWidth
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.paths[root.name] || "" }
        }
    }
}
