# 生成 shield.ico: 矢量盾牌 + 对勾图形, 多尺寸 PNG-in-ICO (16~256px)
import struct
import sys

from PySide6.QtCore import QBuffer, QIODevice, QRectF, QPointF, Qt
from PySide6.QtGui import (QColor, QConicalGradient, QGuiApplication, QPainter,
                           QPainterPath, QPen, QPixmap)

app = QGuiApplication(sys.argv)


def shield_path(size: float) -> QPainterPath:
    """盾形轮廓, 坐标按 256 基准等比缩放。"""
    k = size / 256.0

    def pt(x, y):
        return QPointF(x * k, y * k)

    p = QPainterPath()
    p.moveTo(pt(128, 44))                                   # 顶部中央凹点
    p.cubicTo(pt(104, 44), pt(74, 50), pt(58, 62))          # 左肩
    p.lineTo(pt(58, 116))                                   # 左侧直线
    p.cubicTo(pt(58, 152), pt(92, 184), pt(128, 212))       # 收拢到底部尖角
    p.cubicTo(pt(164, 184), pt(198, 152), pt(198, 116))     # 右侧对称
    p.lineTo(pt(198, 62))
    p.cubicTo(pt(182, 50), pt(152, 44), pt(128, 44))
    p.closeSubpath()
    return p


def render(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    k = size / 256.0

    # 背景圆角方块 + 渐变(左上稍亮)
    grad = QConicalGradient(size * 0.35, size * 0.30, 300)
    grad.setColorAt(0.0, QColor("#22c55e"))
    grad.setColorAt(1.0, QColor("#15803d"))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(8 * k, 8 * k, 240 * k, 240 * k), 54 * k, 54 * k)

    # 白色实心盾牌(底下偏移一层半透明黑做厚度感)
    p.setBrush(QColor(0, 0, 0, 40))
    p.drawPath(QPainterPath(shield_path(size)).translated(QPointF(0, 4 * k)))
    p.setBrush(QColor("white"))
    p.drawPath(shield_path(size))

    # 盾内绿色对勾
    pen = QPen(QColor("#15803d"))
    pen.setWidthF(20 * k)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    check = QPainterPath()
    check.moveTo(QPointF(94 * k, 118 * k))
    check.lineTo(QPointF(120 * k, 144 * k))
    check.lineTo(QPointF(164 * k, 94 * k))
    p.drawPath(check)
    p.end()
    return pm


def to_png(pm: QPixmap) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pm.toImage().save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


sizes = [16, 24, 32, 48, 64, 128, 256]
blobs = [(s, to_png(render(s))) for s in sizes]

header = struct.pack("<HHH", 0, 1, len(blobs))
offset = 6 + 16 * len(blobs)
entries = b""
for s, png in blobs:
    w = 0 if s >= 256 else s
    entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(png), offset)
    offset += len(png)

with open("shield.ico", "wb") as f:
    f.write(header + entries + b"".join(png for _, png in blobs))

# 预览图供人工检查
with open("shield-preview.png", "wb") as f:
    f.write(blobs[-1][1])

print("shield.ico OK:", [f"{s}px {len(b)}B" for s, b in blobs])
