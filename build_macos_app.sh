#!/bin/bash
# build_macos_app.sh — 将 PyInstaller 产物打包成 macOS .app
# 在 GitHub Actions macos runner 上执行

set -e

EXE_NAME="ClipboardSanitizer"
APP_NAME="${EXE_NAME}.app"
DIST_DIR="dist"

echo "=== 创建 .app 捆绑包 ==="

# 1. 清理旧包
rm -rf "${APP_NAME}"

# 2. 创建目录结构
mkdir -p "${APP_NAME}/Contents/MacOS"
mkdir -p "${APP_NAME}/Contents/Resources"

# 3. 拷贝可执行文件
cp "${DIST_DIR}/${EXE_NAME}" "${APP_NAME}/Contents/MacOS/${EXE_NAME}"
chmod +x "${APP_NAME}/Contents/MacOS/${EXE_NAME}"

# 4. 如果有背景图，一并打包
if [ -f "background.png" ]; then
    cp "background.png" "${APP_NAME}/Contents/Resources/"
    echo "  ✅ 已包含背景图"
fi

# 5. 生成图标 (利用 iconutil + 脚本生成的 PNG)
if [ -f "icons/icon128.png" ]; then
    ICONSET="${EXE_NAME}.iconset"
    rm -rf "${ICONSET}"
    mkdir -p "${ICONSET}"
    # 从 128x128 PNG 生成各种尺寸
    sips -z 16 16   icons/icon128.png --out "${ICONSET}/icon_16x16.png"      2>/dev/null
    sips -z 32 32   icons/icon128.png --out "${ICONSET}/icon_16x16@2x.png"   2>/dev/null
    sips -z 32 32   icons/icon128.png --out "${ICONSET}/icon_32x32.png"      2>/dev/null
    sips -z 64 64   icons/icon128.png --out "${ICONSET}/icon_32x32@2x.png"   2>/dev/null
    sips -z 128 128 icons/icon128.png --out "${ICONSET}/icon_128x128.png"    2>/dev/null
    sips -z 256 256 icons/icon128.png --out "${ICONSET}/icon_256x256.png"    2>/dev/null
    sips -z 256 256 icons/icon128.png --out "${ICONSET}/icon_128x128@2x.png" 2>/dev/null
    sips -z 512 512 icons/icon128.png --out "${ICONSET}/icon_512x512.png"    2>/dev/null
    iconutil -c icns "${ICONSET}" -o "${APP_NAME}/Contents/Resources/icon.icns" 2>/dev/null || true
    rm -rf "${ICONSET}"
    echo "  ✅ 已生成图标"
fi

# 6. 创建 Info.plist
cat > "${APP_NAME}/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>zh_CN</string>
    <key>CFBundleExecutable</key>
    <string>ClipboardSanitizer</string>
    <key>CFBundleIdentifier</key>
    <string>com.clipboard.sanitizer</string>
    <key>CFBundleName</key>
    <string>剪贴板净化器</string>
    <key>CFBundleDisplayName</key>
    <string>剪贴板净化器</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
</dict>
</plist>
PLIST

echo ""
echo "=== ✅ .app 创建完成 ==="
echo "  ${APP_NAME}"
echo ""
echo "使用方式：双击 ${APP_NAME} 即可启动（无需终端）"
echo "如需自定义背景，将图片命名为 background.png 放入"
echo "  ${APP_NAME}/Contents/Resources/"
