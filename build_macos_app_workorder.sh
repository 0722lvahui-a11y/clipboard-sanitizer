#!/bin/bash
# build_macos_app_workorder.sh
# 将 PyInstaller 产物打包成 macOS .app（工单act_计数工具）
# 不打包浏览器 — 使用系统自带的 Chrome

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

# 4. 可选背景图
if [ -f "background.png" ]; then
    cp "background.png" "${APP_NAME}/Contents/Resources/"
    echo "  ✅ 已包含背景图"
fi

# 5. 生成图标
echo "  生成应用图标..."
python3 -c "
import struct, zlib, os
os.makedirs('icons_wk', exist_ok=True)

def icon_pixel(x, y, s):
    cx, cy = x/s, y/s
    margin, radius = 0.08, 0.15
    if cx < margin or cx > 1-margin or cy < margin or cy > 1-margin:
        return (0,0,0,0)
    # 粉色前景
    r, g, b = 0xE8, 0xB4, 0xB8
    for ly in [0.35, 0.50, 0.65]:
        if abs(cy-ly) < 0.04 and 0.2 < cx < 0.8:
            r, g, b = 255, 255, 255
    if 0.65 < cx < 0.82 and 0.20 < cy < 0.45:
        r, g, b = 0xD4, 0x91, 0x9E
    return (r, g, b, 255)

def make_png(size, outpath):
    raw = b''
    for y in range(size):
        raw += b'\x00'
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
    [ -f "${APP_NAME}/Contents/Resources/icon.icns" ] && echo "  ✅ 应用图标已生成"
fi
rm -rf icons_wk

# 6. 创建 Info.plist
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
</dict>
</plist>
PLIST

SIZE=$(du -sh "${APP_NAME}" | cut -f1)
echo ""
echo "=== ✅ .app 创建完成 ==="
echo "  ${APP_NAME}  (${SIZE})"
echo ""
echo "双击 ${APP_NAME} 即可启动"
echo "💡 使用系统 Chrome 浏览器，无需额外安装"
