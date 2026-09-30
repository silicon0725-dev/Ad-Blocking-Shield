import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 412
    height: 742
    minimumWidth: 400
    minimumHeight: 700
    visible: true
    title: "广告拦截控制台"
    color: "#0b0f15"

    Material.theme: Material.Dark
    Material.primary: "#22c55e"
    Material.accent: "#22c55e"

    property string fontMain: "Microsoft YaHei UI"

    // ============ 背景渐变 ============
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0b0f15" }
            GradientStop { position: 0.5; color: "#0c1220" }
            GradientStop { position: 1.0; color: "#0a0e14" }
        }
        Rectangle {
            width: 300; height: 300
            anchors { top: parent.top; horizontalCenter: parent.horizontalCenter }
            anchors.topMargin: -180
            radius: 150
            color: Backend.enabled ? "#12291c" : "#10151d"
            opacity: 0.55
        }
    }

    // ============ 整体布局 ============
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- 顶部标题 ----
        RowLayout {
            Layout.margins: 16
            Layout.bottomMargin: 8
            spacing: 12

            Rectangle {
                width: 40; height: 40; radius: 12
                color: Backend.enabled ? "#17301f" : "#1a2029"
                border.color: Backend.enabled ? "#2c5e3f" : "#242d38"
                border.width: 1
                Image {
                    anchors.centerIn: parent
                    width: 24; height: 24
                    source: "icons/shield-check.svg"
                    opacity: Backend.enabled ? 1.0 : 0.45
                }
                Behavior on border.color { ColorAnimation { duration: 400 } }
            }
            ColumnLayout {
                spacing: 2
                Text {
                    text: "广告拦截控制台"
                    color: "#f1f5f9"; font.pixelSize: 17; font.bold: true
                    font.family: root.fontMain
                }
                Text {
                    text: Backend.domainOnly
                          ? "仅域名拦截 · 不解密 · 低功耗"
                          : (Backend.enabled ? "完整拦截 · 域名 + 路径规则"
                                             : "已停用 — 浏览器直连 Clash")
                    color: "#71808f"; font.pixelSize: 11
                    font.family: root.fontMain
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: statusPillText.implicitWidth + 30; height: 26; radius: 13
                color: Backend.enabled ? "#132a1b" : "#241a1a"
                border.color: Backend.enabled ? "#2c5e3f" : "#4a2626"
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 6
                    Rectangle {
                        width: 7; height: 7; radius: 3.5
                        color: Backend.enabled ? "#4ade80" : "#f87171"
                        SequentialAnimation on opacity {
                            running: Backend.enabled && root.visible && !Backend.moving
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.35; duration: 1100; easing.type: Easing.InOutQuad }
                            NumberAnimation { to: 1.0; duration: 1100; easing.type: Easing.InOutQuad }
                        }
                    }
                    Text {
                        id: statusPillText
                        text: Backend.enabled ? "运行中" : "已停用"
                        color: Backend.enabled ? "#86efac" : "#fca5a5"
                        font.pixelSize: 11; font.bold: true
                        font.family: root.fontMain
                    }
                }
            }
        }

        // ---- 标签栏 ----
        TabBar {
            id: tabBar
            Layout.fillWidth: true
            Layout.margins: 16
            Layout.topMargin: 0
            background: Rectangle { color: "transparent" }
            TabButton {
                text: "状态"
                font.family: root.fontMain
                width: tabBar.width / 3
            }
            TabButton {
                text: "拦截日志"
                font.family: root.fontMain
                width: tabBar.width / 3
            }
            TabButton {
                text: "设置"
                font.family: root.fontMain
                width: tabBar.width / 3
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: "#1a222e"
            Layout.margins: 16; Layout.topMargin: 0 }

        // ---- 页面 ----
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // ================ 第 1 页: 状态 ================
            Item {
                ColumnLayout {
                    id: pageStatus
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 108
                    radius: 16
                    color: "#121824"
                    border.color: Backend.enabled ? "#1f3a2a" : "#1c2430"
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 16
                        Item {
                            Layout.preferredWidth: 68; Layout.preferredHeight: 68
                            Rectangle {
                                anchors.centerIn: parent
                                width: 68; height: 68; radius: 34
                                color: "transparent"
                                border.color: "#22c55e"; border.width: 1
                                opacity: 0
                                visible: Backend.enabled
                                SequentialAnimation on opacity {
                                    running: Backend.enabled && root.visible && !Backend.moving
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.12; duration: 1500; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 0.5; duration: 1500; easing.type: Easing.InOutSine }
                                }
                                scale: 1.12
                            }
                            Rectangle {
                                anchors.centerIn: parent
                                width: 58; height: 58; radius: 29
                                color: powerMa.containsMouse ? (Backend.enabled ? "#2fdf6f" : "#425062")
                                                             : (Backend.enabled ? "#22c55e" : "#2c3746")
                                border.color: Backend.enabled ? "#6ee7a0" : "#3d4a5c"
                                border.width: 1
                                scale: powerMa.pressed ? 0.93 : 1.0
                                Behavior on color { ColorAnimation { duration: 150 } }
                                Behavior on scale { NumberAnimation { duration: 100 } }
                                Image {
                                    anchors.centerIn: parent
                                    width: 26; height: 26
                                    source: "icons/power.svg"
                                    opacity: Backend.enabled ? 1.0 : 0.55
                                }
                            }
                            MouseArea {
                                id: powerMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Backend.toggle()
                            }
                        }
                        ColumnLayout {
                            spacing: 4
                            RowLayout {
                                spacing: 8
                                Text {
                                    text: Backend.enabled ? "广告拦截运行中" : "广告拦截已停用"
                                    color: "#f1f5f9"; font.pixelSize: 16; font.bold: true
                                    font.family: root.fontMain
                                }
                                Rectangle {
                                    visible: Backend.enabled
                                    width: rulesPill.implicitWidth + 16; height: 20; radius: 10
                                    color: "#132a1b"
                                    Text {
                                        id: rulesPill
                                        anchors.centerIn: parent
                                        text: Backend.ruleCount.toLocaleString() + " 条规则"
                                        color: "#86efac"; font.pixelSize: 10
                                        font.family: root.fontMain
                                    }
                                }
                            }
                            Text {
                                text: Backend.enabled
                                      ? (Backend.domainOnly ? "按域名拦截, 全程不解密 HTTPS"
                                                            : "规则命中才解密过滤 · 其余站点零解密直通")
                                      : "点击左侧电源按钮一键启用"
                                color: "#71808f"; font.pixelSize: 12
                                font.family: root.fontMain
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 12
                    Repeater {
                        model: [
                            { icon: "icons/server.svg",      label: "MITM 服务",  ok: Backend.mitmRunning, on: "运行中", off: "未运行",
                              tip: "mitmproxy HTTPS 过滤服务\n监听 127.0.0.1:8080，负责解密与广告过滤" },
                            { icon: "icons/globe.svg",       label: "系统代理",   ok: Backend.proxyOurs, on: Backend.proxyServer, off: "直连 / Clash",
                              tip: "Windows 系统代理当前指向\n8080 = 经广告过滤，7897 = 直连 Clash" },
                            { icon: "icons/network.svg",     label: "TUN · Mihomo", ok: Backend.tunUp && Backend.coreUp, on: "正常接管", off: "未运行",
                              tip: "Clash Verge 的 TUN 模式\n保持系统全局流量接管，本工具不修改它" },
                            { icon: "icons/badge-check.svg", label: "CA 证书",    ok: Backend.caOk, on: "已信任", off: "未安装",
                              tip: "mitmproxy 根证书（仅本机用户存储）\n仅域名拦截模式下不需要它" }
                        ]
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 62
                            radius: 12
                            color: "#121824"
                            border.color: "#1c2430"; border.width: 1
                            HoverHandler { id: chipHover }
                            ToolTip.visible: chipHover.hovered
                            ToolTip.delay: 400
                            ToolTip.text: modelData.tip
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 11
                                spacing: 10
                                Rectangle {
                                    Layout.preferredWidth: 36; Layout.preferredHeight: 36
                                    radius: 9
                                    color: modelData.ok ? "#132a1b" : "#221a1a"
                                    Image {
                                        anchors.centerIn: parent
                                        width: 18; height: 18
                                        source: modelData.icon
                                        opacity: modelData.ok ? 0.95 : 0.5
                                    }
                                }
                                ColumnLayout {
                                    spacing: 2
                                    RowLayout {
                                        spacing: 5
                                        Text {
                                            text: modelData.label
                                            color: "#71808f"; font.pixelSize: 10
                                            font.family: root.fontMain
                                        }
                                        Rectangle {
                                            width: 6; height: 6; radius: 3
                                            color: modelData.ok ? "#4ade80" : "#f87171"
                                        }
                                    }
                                    Text {
                                        text: modelData.ok ? modelData.on : modelData.off
                                        color: modelData.ok ? "#e2e8f0" : "#8b98a8"
                                        font.pixelSize: 13; font.bold: true
                                        font.family: root.fontMain
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 16
                    color: "#121824"
                    border.color: "#1c2430"; border.width: 1
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10
                        RowLayout {
                            spacing: 8
                            Image { width: 16; height: 16; source: "icons/chart-column.svg" }
                            Text {
                                text: "拦截统计"
                                color: "#8b98a8"; font.pixelSize: 12; font.bold: true
                                font.family: root.fontMain
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: "Top 6 域名"
                                color: "#4b5563"; font.pixelSize: 10
                                font.family: root.fontMain
                            }
                        }
                        RowLayout {
                            spacing: 12
                            Rectangle {
                                Layout.fillWidth: true; Layout.preferredHeight: 64
                                radius: 11; color: "#0f1a14"
                                border.color: "#1a2f22"; border.width: 1
                                ColumnLayout {
                                    anchors.centerIn: parent; spacing: 2
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: Backend.blockedToday.toLocaleString()
                                        color: "#4ade80"; font.pixelSize: 23; font.bold: true
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "今日拦截"; color: "#71808f"; font.pixelSize: 11
                                        font.family: root.fontMain
                                    }
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true; Layout.preferredHeight: 64
                                radius: 11; color: "#0f1522"
                                border.color: "#1a2436"; border.width: 1
                                ColumnLayout {
                                    anchors.centerIn: parent; spacing: 2
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: Backend.blockedTotal.toLocaleString()
                                        color: "#60a5fa"; font.pixelSize: 23; font.bold: true
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "累计拦截"; color: "#71808f"; font.pixelSize: 11
                                        font.family: root.fontMain
                                    }
                                }
                            }
                        }
                        ListView {
                            id: topList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: Backend.topDomains
                            spacing: 5
                            delegate: RowLayout {
                                width: topList.width
                                spacing: 8
                                Rectangle {
                                    Layout.preferredWidth: 18; Layout.preferredHeight: 18
                                    radius: 9
                                    color: index === 0 ? "#17301f" : index === 1 ? "#182334" : "#1a2029"
                                    Text {
                                        anchors.centerIn: parent
                                        text: index + 1
                                        color: index === 0 ? "#4ade80" : index === 1 ? "#60a5fa" : "#64748b"
                                        font.pixelSize: 10; font.bold: true
                                    }
                                }
                                Text {
                                    text: modelData.host
                                    color: "#cbd5e1"; font.pixelSize: 12
                                    font.family: root.fontMain
                                    elide: Text.ElideMiddle
                                    Layout.preferredWidth: topList.width * 0.46
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 7
                                    radius: 3.5
                                    color: "#1a212c"
                                    Rectangle {
                                        visible: topList.count > 0
                                        width: Math.min(1.0, 0.12 + 0.88 * (topList.count > 1
                                             ? modelData.count / Backend.topDomains[0].count : 1)) * parent.width
                                        height: parent.height
                                        radius: 3.5
                                        color: index === 0 ? "#34d399" : index < 3 ? "#3b82f6" : "#64748b"
                                        opacity: 0.85
                                        Behavior on width { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
                                    }
                                }
                                Text {
                                    text: modelData.count
                                    color: "#64748b"; font.pixelSize: 11
                                    Layout.preferredWidth: 26
                                    horizontalAlignment: Text.AlignRight
                                }
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: topList.count === 0
                                text: "暂无拦截记录\n浏览网页后此处显示统计"
                                color: "#4b5563"; font.pixelSize: 12
                                font.family: root.fontMain
                                horizontalAlignment: Text.AlignHCenter
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 38; radius: 10
                        color: updateMa.containsHover ? "#1a2433" : "#141b26"
                        border.color: "#223042"; border.width: 1
                        RowLayout { anchors.centerIn: parent; spacing: 7
                            Image { width: 14; height: 14; source: "icons/refresh-cw.svg" }
                            Text { text: "更新规则"; color: "#cbd5e1"; font.pixelSize: 12
                                   font.family: root.fontMain } }
                        HoverHandler { id: updateMa; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: Backend.updateLists() }
                    }
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 38; radius: 10
                        color: logMa.containsHover ? "#1a2433" : "#141b26"
                        border.color: "#223042"; border.width: 1
                        RowLayout { anchors.centerIn: parent; spacing: 7
                            Image { width: 14; height: 14; source: "icons/file-text.svg" }
                            Text { text: "原始日志"; color: "#cbd5e1"; font.pixelSize: 12
                                   font.family: root.fontMain } }
                        HoverHandler { id: logMa; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: Backend.openBlockedLog() }
                    }
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 38; radius: 10
                        color: rbMa.containsHover ? "#2a1a1a" : "#1d1416"
                        border.color: "#4a2626"; border.width: 1
                        RowLayout { anchors.centerIn: parent; spacing: 7
                            Image { width: 14; height: 14; source: "icons/rotate-ccw.svg" }
                            Text { text: "彻底回滚"; color: "#fca5a5"; font.pixelSize: 12
                                   font.family: root.fontMain } }
                        HoverHandler { id: rbMa; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: confirmDialog.open() }
                    }
                }
                }
            }

            // ================ 第 2 页: 拦截日志 ================
            Item {
                ColumnLayout {
                    id: pageLog
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                RowLayout {
                    spacing: 8
                    Image { width: 15; height: 15; source: "icons/file-text.svg" }
                    Text {
                        text: "最近拦截记录"
                        color: "#8b98a8"; font.pixelSize: 12; font.bold: true
                        font.family: root.fontMain
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "点 ＋白 放行该域名 (≤10秒生效)"
                        color: "#4b5563"; font.pixelSize: 10
                        font.family: root.fontMain
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 16
                    color: "#121824"
                    border.color: "#1c2430"; border.width: 1

                    ListView {
                        id: recentList
                        anchors.fill: parent
                        anchors.margins: 8
                        clip: true
                        model: Backend.recentBlocks
                        spacing: 2
                        ScrollBar.vertical: ScrollBar {}

                        delegate: Rectangle {
                            width: recentList.width
                            height: 52
                            radius: 8
                            color: rowHover.hovered ? "#161e2b" : "transparent"

                            HoverHandler { id: rowHover }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 4
                                spacing: 8

                                ColumnLayout {
                                    spacing: 2
                                    Layout.fillWidth: true
                                    RowLayout {
                                        spacing: 6
                                        Text {
                                            text: modelData.time
                                            color: "#5b6774"; font.pixelSize: 10
                                            font.family: "Consolas"
                                        }
                                        Rectangle {
                                            width: srcLbl.implicitWidth + 10; height: 15; radius: 7
                                            color: modelData.src === "user-blacklist" ? "#331b1b" : "#14202e"
                                            Text {
                                                id: srcLbl
                                                anchors.centerIn: parent
                                                text: modelData.src.replace("easylistchina.txt", "中国").replace("easylist.txt", "主表").replace(".txt", "")
                                                color: modelData.src === "user-blacklist" ? "#fca5a5" : "#7ba3d7"
                                                font.pixelSize: 9
                                                font.family: root.fontMain
                                            }
                                        }
                                        Text {
                                            text: modelData.host
                                            color: "#e2e8f0"; font.pixelSize: 12; font.bold: true
                                            font.family: root.fontMain
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }
                                    }
                                    Text {
                                        text: (modelData.path.length > 1 ? modelData.path + "  ←  " : "") + modelData.rule
                                        color: "#5b6774"; font.pixelSize: 10
                                        font.family: root.fontMain
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }

                                Rectangle {
                                    Layout.preferredWidth: 44; Layout.preferredHeight: 26
                                    radius: 6
                                    color: wlMa.containsHover ? "#1d3a27" : "#152b1d"
                                    border.color: "#2c5e3f"; border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "＋白"
                                        color: "#86efac"; font.pixelSize: 11; font.bold: true
                                        font.family: root.fontMain
                                    }
                                    HoverHandler { id: wlMa; cursorShape: Qt.PointingHandCursor }
                                    TapHandler { onTapped: Backend.addWhitelist(modelData.host) }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: recentList.count === 0
                            text: "暂无拦截记录\n浏览网页后此处显示最近 150 条"
                            color: "#4b5563"; font.pixelSize: 12
                            font.family: root.fontMain
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                    }
                }
            }

            // ================ 第 3 页: 设置 ================
            Flickable {
                id: pageSettings
                contentWidth: width
                contentHeight: settingsCol.implicitHeight + 32
                clip: true
                ScrollBar.vertical: ScrollBar {}

                ColumnLayout {
                    id: settingsCol
                    x: 16
                    width: pageSettings.width - 32
                    spacing: 12

                    // ---- 拦截模式 ----
                    Rectangle {
                        Layout.fillWidth: true; height: 84; radius: 14
                        color: "#121824"; border.color: "#1c2430"; border.width: 1
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 14; spacing: 3
                            Item { Layout.fillHeight: true }
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "仅域名拦截（低功耗模式）"
                                    color: "#e2e8f0"; font.pixelSize: 13; font.bold: true
                                    font.family: root.fontMain
                                }
                                Item { Layout.fillWidth: true }
                                Switch {
                                    checked: Backend.domainOnly
                                    onToggled: Backend.setDomainOnly(checked)
                                }
                            }
                            Text {
                                text: "不解密任何 HTTPS（真实证书直通），只在 CONNECT 阶段按域名拦截。\nCPU 几乎为零、兼容性最好，但路径级规则失效（约损失 1/4 拦截量）。"
                                color: "#5b6774"; font.pixelSize: 10; lineHeight: 1.3
                                font.family: root.fontMain
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true; height: 56; radius: 14
                        color: "#10161f"; border.color: "#1b2634"; border.width: 1
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 14; spacing: 2
                            Item { Layout.fillHeight: true }
                            Text {
                                text: "当前完整模式已升级为「精准解密」：仅命中广告规则的域名解密过滤，其余全部隧道直通（浏览器原始 TLS 直达源站，大厂站点不再 502）"
                                color: "#4b6b8a"; font.pixelSize: 10; lineHeight: 1.3
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                font.family: root.fontMain
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }

                    // ---- 开机自启 ----
                    Rectangle {
                        Layout.fillWidth: true; height: 70; radius: 14
                        color: "#121824"; border.color: "#1c2430"; border.width: 1
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 14; spacing: 3
                            Item { Layout.fillHeight: true }
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "开机自动启动并恢复拦截"
                                    color: "#e2e8f0"; font.pixelSize: 13; font.bold: true
                                    font.family: root.fontMain
                                }
                                Item { Layout.fillWidth: true }
                                Switch {
                                    checked: Backend.autoStart
                                    onToggled: Backend.setAutoStart(checked)
                                }
                            }
                            Text {
                                text: "开机后静默到托盘，等 Clash 就绪后自动开启拦截"
                                color: "#5b6774"; font.pixelSize: 10
                                font.family: root.fontMain
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }

                    // ---- 白名单 ----
                    DomainListEditor {
                        Layout.fillWidth: true
                        title: "放行白名单（优先级最高，解决误杀）"
                        placeholder: "例如 example.com（含子域）"
                        accentDot: "#4ade80"
                        domains: Backend.userWhitelist
                        onAdd: (d) => Backend.addWhitelist(d)
                        onRemove: (d) => Backend.removeWhitelist(d)
                    }

                    // ---- 黑名单 ----
                    DomainListEditor {
                        Layout.fillWidth: true
                        title: "强制黑名单（拦规则表漏掉的域名）"
                        placeholder: "例如 ads.example.com"
                        accentDot: "#f87171"
                        domains: Backend.userBlacklist
                        onAdd: (d) => Backend.addBlacklist(d)
                        onRemove: (d) => Backend.removeBlacklist(d)
                    }

                    // ---- MITM 直通名单 ----
                    DomainListEditor {
                        Layout.fillWidth: true
                        title: "MITM 直通（不解密：修复 502 / 证书校验问题）"
                        placeholder: "例如 chatgpt.com"
                        accentDot: "#60a5fa"
                        domains: Backend.userBypass
                        onAdd: (d) => Backend.addBypass(d)
                        onRemove: (d) => Backend.removeBypass(d)
                    }

                    // ---- 规则源 ----
                    Rectangle {
                        Layout.fillWidth: true; radius: 14
                        color: "#121824"; border.color: "#1c2430"; border.width: 1
                        implicitHeight: srcCol.implicitHeight + 24
                        ColumnLayout {
                            id: srcCol
                            anchors.fill: parent; anchors.margins: 12; spacing: 8
                            Text {
                                text: "规则源订阅"
                                color: "#8b98a8"; font.pixelSize: 12; font.bold: true
                                font.family: root.fontMain
                            }
                            Repeater {
                                model: Backend.sources
                                Rectangle {
                                    Layout.fillWidth: true; height: 44; radius: 8
                                    color: modelData.enabled ? "#141c28" : "#11151c"
                                    border.color: "#1e2836"; border.width: 1
                                    RowLayout {
                                        anchors.fill: parent; anchors.margins: 8; spacing: 8
                                        ColumnLayout {
                                            spacing: 1
                                            Layout.fillWidth: true
                                            Text {
                                                text: modelData.name + (modelData.enabled ? "" : " （已停用）")
                                                color: modelData.enabled ? "#e2e8f0" : "#5b6774"
                                                font.pixelSize: 12; font.bold: true
                                                font.family: root.fontMain
                                            }
                                            Text {
                                                text: modelData.url
                                                color: "#4b5563"; font.pixelSize: 9
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                            }
                                        }
                                        Switch {
                                            checked: modelData.enabled
                                            onToggled: Backend.toggleSource(modelData.name)
                                        }
                                        Rectangle {
                                            visible: !modelData.builtin
                                            width: 30; height: 26; radius: 6
                                            color: rmSrc.hovered ? "#331b1b" : "#241616"
                                            border.color: "#4a2626"; border.width: 1
                                            Text { anchors.centerIn: parent; text: "✕"
                                                   color: "#fca5a5"; font.pixelSize: 11 }
                                            HoverHandler { id: rmSrc; cursorShape: Qt.PointingHandCursor }
                                            TapHandler { onTapped: Backend.removeSource(modelData.name) }
                                        }
                                    }
                                }
                            }
                            RowLayout {
                                spacing: 8
                                TextField {
                                    id: srcName
                                    Layout.preferredWidth: 100
                                    placeholderText: "名称(英文)"
                                    font.pixelSize: 11
                                    color: "#e2e8f0"
                                    background: Rectangle { radius: 6; color: "#0f1522"
                                        border.color: srcName.activeFocus ? "#2c5e3f" : "#1e2836" }
                                }
                                TextField {
                                    id: srcUrl
                                    Layout.fillWidth: true
                                    placeholderText: "https://…/list.txt 规则订阅 URL"
                                    font.pixelSize: 11
                                    color: "#e2e8f0"
                                    background: Rectangle { radius: 6; color: "#0f1522"
                                        border.color: srcUrl.activeFocus ? "#2c5e3f" : "#1e2836" }
                                }
                                Rectangle {
                                    width: 52; height: 34; radius: 8
                                    color: addSrc.hovered ? "#1d3a27" : "#152b1d"
                                    border.color: "#2c5e3f"; border.width: 1
                                    Text { anchors.centerIn: parent; text: "添加"
                                           color: "#86efac"; font.pixelSize: 11
                                           font.family: root.fontMain }
                                    HoverHandler { id: addSrc; cursorShape: Qt.PointingHandCursor }
                                    TapHandler { onTapped: { Backend.addSource(srcName.text, srcUrl.text)
                                                             srcName.clear(); srcUrl.clear() } }
                                }
                            }
                        }
                    }

                    Item { width: 1; height: 4 }
                }
            }
        }

        // ---- 底部 ----
        Rectangle {
            Layout.fillWidth: true; height: 30
            color: "#0a0d12"
            Text {
                anchors.centerIn: parent
                text: "关闭窗口将最小化到系统托盘 · 右键托盘图标可快捷启停"
                color: "#4b5563"; font.pixelSize: 10
                font.family: root.fontMain
            }
        }
    }

    // ============ 域名列表编辑器组件 ============
    component DomainListEditor : Rectangle {
        id: editor
        property string title
        property string placeholder
        property color accentDot
        property var domains: []
        signal add(string domain)
        signal remove(string domain)

        radius: 14
        color: "#121824"
        border.color: "#1c2430"; border.width: 1
        implicitHeight: inner.implicitHeight + 24

        ColumnLayout {
            id: inner
            anchors.fill: parent; anchors.margins: 12; spacing: 8
            RowLayout {
                spacing: 6
                Rectangle { width: 7; height: 7; radius: 3.5; color: editor.accentDot }
                Text {
                    text: editor.title
                    color: "#8b98a8"; font.pixelSize: 12; font.bold: true
                    font.family: root.fontMain
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: editor.domains.length + " 条"
                    color: "#4b5563"; font.pixelSize: 10
                    font.family: root.fontMain
                }
            }
            RowLayout {
                spacing: 8
                TextField {
                    id: input
                    Layout.fillWidth: true
                    placeholderText: editor.placeholder
                    font.pixelSize: 11
                    color: "#e2e8f0"
                    font.family: root.fontMain
                    background: Rectangle { radius: 6; color: "#0f1522"
                        border.color: input.activeFocus ? "#2c5e3f" : "#1e2836" }
                    onAccepted: { if (text.trim()) { editor.add(text); clear() } }
                }
                Rectangle {
                    width: 52; height: 34; radius: 8
                    color: addBtn.hovered ? "#1d3a27" : "#152b1d"
                    border.color: "#2c5e3f"; border.width: 1
                    Text { anchors.centerIn: parent; text: "添加"
                           color: "#86efac"; font.pixelSize: 11
                           font.family: root.fontMain }
                    HoverHandler { id: addBtn; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: { if (input.text.trim()) { editor.add(input.text); input.clear() } } }
                }
            }
            ListView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(4, editor.domains.length) * 30
                visible: editor.domains.length > 0
                clip: true
                model: editor.domains
                spacing: 2
                delegate: RowLayout {
                    width: parent ? parent.width : 0
                    height: 28
                    spacing: 8
                    Text {
                        text: modelData
                        color: "#cbd5e1"; font.pixelSize: 11
                        font.family: root.fontMain
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    Rectangle {
                        width: 30; height: 24; radius: 6
                        color: rmBtn.hovered ? "#331b1b" : "#241616"
                        border.color: "#4a2626"; border.width: 1
                        Text { anchors.centerIn: parent; text: "✕"
                               color: "#fca5a5"; font.pixelSize: 11 }
                        HoverHandler { id: rmBtn; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: editor.remove(modelData) }
                    }
                }
            }
        }
    }

    // ============ 回滚确认 ============
    Dialog {
        id: confirmDialog
        anchors.centerIn: parent
        modal: true
        width: 330
        title: "彻底回滚"
        contentItem: ColumnLayout {
            spacing: 10
            Text {
                text: "将执行以下操作:\n  1. 停止 mitmproxy\n  2. 系统代理恢复 → 127.0.0.1:7897\n  3. 删除 mitmproxy CA 证书\n\nClash / TUN / 节点配置不受任何影响。"
                color: "#cbd5e1"; font.pixelSize: 13
                font.family: root.fontMain
                lineHeight: 1.25
            }
        }
        footer: DialogButtonBox {
            Button { flat: true; text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button {
                text: "确认回滚"
                Material.background: "#b91c1c"
                Material.foreground: "white"
                onClicked: { Backend.rollback(); confirmDialog.close() }
            }
        }
    }
}
