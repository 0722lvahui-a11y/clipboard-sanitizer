#!/bin/bash
# build_macos_app_workorder.sh
# 将 PyInstaller 产物打包成 macOS .app（工单act_计数工具）
# 在 GitHub Actions macos runner 上执行

set -e

EXE_NAME="WorkorderActCounter"
APP_NAME="${EXE_NAME}.app"
DIST_DIR="dist"

echo "=== 创建 .app 捆绑包 (工单act_计数工具) ==="

# 1. 清理旧包
rm -rf "${APP_NAME}"

# 2. 创建目录结构
mkdir -p "${APP_NAME}/Contents/MacOS"
mkdir -p "${APP_NAME}/Contents/Resources"

# 3. 拷贝可执行文件
cp "${DIST_DIR}/${EXE_NAME}" "${APP_NAME}/Contents/MacOS/${EXE_NAME}"
chmod +x "${APP_NAME}/Contents/MacOS/${EXE_NAME}"

# 4. 打包 Playwright Chromium 浏览器
echo "  查找 Playwright 浏览器..."
BROWSERS_SRC=""
if [ -d "$HOME/Library/Caches/ms-playwright" ]; then
    BROWSERS_SRC="$HOME/Library/Caches/ms-playwright"
elif [ -d "$HOME/.cache/ms-playwright" ]; then
    BROWSERS_SRC="$HOME/.cache/ms-playwright"
fi

if [ -n "$BROWSERS_SRC" ] && [ -d "$BROWSERS_SRC" ]; then
    echo "  复制 Playwright 浏览器到 .app..."
    cp -r "$BROWSERS_SRC" "${APP_NAME}/Contents/Resources/ms-playwright"
    echo "  ✅ 浏览器已打包 ($(du -sh "$BROWSERS_SRC" | cut -f1))"
else
    echo "  ⚠️  未找到 Playwright 浏览器缓存，.app 将需要系统安装 Chromium"
fi

# 5. 如果有背景图，一并打包
if [ -f "background.png" ]; then
    cp "background.png" "${APP_NAME}/Contents/Resources/"
    echo "  ✅ 已包含背景图"
fi

# 6. 生成图标 (📋 剪贴板计数风格)
echo "  生成应用图标..."
python3 -c "
import struct, zlib, os
os.makedirs('icons_wk', exist_ok=True)

# 简单图标：粉色背景 + 白色列表/计数符号
def icon_pixel(x, y, s):
    '返回 (R, G, B, A) for 图标像素'
    cx, cy = x / s, y / s  # 0..1

    # 圆角矩形背景 (粉色)
    margin = 0.08
    radius = 0.15

    # 圆角矩形检测
    def in_rounded_rect(px, py):
        if px < margin or px > 1 - margin or py < margin or py > 1 - margin:
            return False
        # 四角
        for cx_c, cy_c in [(margin+radius, margin+radius),
                            (1-margin-radius, margin+radius),
                            (margin+radius, 1-margin-radius),
                            (1-margin-radius, 1-margin-radius)]:
            dx, dy = px - cx_c, py - cy_c
            if dx*dx + dy*dy < radius*radius:
                return True
            if dx > 0 and dy > 0:
                return False  # 在圆角外
        # 简单处理：非角落区域
        if margin <= px <= 1-margin and margin <= py <= 1-margin:
            return True
        return False

    if in_rounded_rect(cx, cy):
        # 粉色背景
        r, g, b = 0xE8, 0xB4, 0xB8

        # 白色横条 (代表列表行)
        line_ys = [0.35, 0.50, 0.65]
        line_h = 0.04
        for ly in line_ys:
            if abs(cy - ly) < line_h and 0.2 < cx < 0.8:
                r, g, b = 255, 255, 255

        # 数字标记 (右侧)
        if 0.65 < cx < 0.82 and 0.20 < cy < 0.45:
            # 小数字区域 - 亮色
            r, g, b = 0xD4, 0x91, 0x9E

        return (r, g, b, 255)

    return (0, 0, 0, 0)

def make_png(size, outpath):
    raw = b''
    for y in range(size):
        raw += b'\x00'  # filter byte
        for x in range(size):
            raw += struct.pack('BBBB', *icon_pixel(x, y, size))

    def chunk(ctype, data):
        c2 = ctype + data
        return struct.pack('>I', len(data)) + c2 + struct.pack('>I', zlib.crc32(c2) & 0xffffffff)

    with open(outpath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(raw)))
        f.write(chunk(b'IEND', b''))

for sz, fn in [(16, 'icons_wk/icon16.png'), (48, 'icons_wk/icon48.png'), (128, 'icons_wk/icon128.png')]:
    make_png(sz, fn)
print('  图标 PNG 已生成')
"

if [ -f "icons_wk/icon128.png" ]; then
    ICONSET="${EXE_NAME}.iconset"
    rm -rf "${ICONSET}"
    mkdir -p "${ICONSET}"
    sips -z 16 16   icons_wk/icon128.png --out "${ICONSET}/icon_16x16.png"      2>/dev/null || true
    sips -z 32 32   icons_wk/icon128.png --out "${ICONSET}/icon_16x16@2x.png"   2>/dev/null || true
    sips -z 32 32   icons_wk/icon128.png --out "${ICONSET}/icon_32x32.png"      2>/dev/null || true
    sips -z 64 64   icons_wk/icon128.png --out "${ICONSET}/icon_32x32@2x.png"   2>/dev/null || true
    sips -z 128 128 icons_wk/icon128.png --out "${ICONSET}/icon_128x128.png"    2>/dev/null || true
    sips -z 256 256 icons_wk/icon128.png --out "${ICONSET}/icon_256x256.png"    2>/dev/null || true
    sips -z 256 256 icons_wk/icon128.png --out "${ICONSET}/icon_128x128@2x.png" 2>/dev/null || true
    sips -z 512 512 icons_wk/icon128.png --out "${ICONSET}/icon_512x512.png"    2>/dev/null || true
    iconutil -c icns "${ICONSET}" -o "${APP_NAME}/Contents/Resources/icon.icns" 2>/dev/null || true
    rm -rf "${ICONSET}"
    if [ -f "${APP_NAME}/Contents/Resources/icon.icns" ]; then
        echo "  ✅ 应用图标已生成"
    fi
fi
rm -rf icons_wk

# 7. 创建 Info.plist
cat > "${APP_NAME}/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>zh_CN</string>
    <key>CFBundleExecutable</key>
    <string>WorkorderActCounter</string>
    <key>CFBundleIdentifier</key>
    <string>com.workorder.actcounter</string>
    <key>CFBundleName</key>
    <string>工单act_计数</string>
    <key>CFBundleDisplayName</key>
    <string>工单act_计数工具</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>LSEnvironment</key>
    <dict>
        <key>PLAYWRIGHT_BROWSERS_PATH</key>
        <string>./Contents/Resources/ms-playwright</string>
    </dict>
</dict>
</plist>
PLIST

echo ""
echo "=== ✅ .app 创建完成 ==="
echo "  ${APP_NAME}"
echo ""
echo "双击 ${APP_NAME} 即可启动"
