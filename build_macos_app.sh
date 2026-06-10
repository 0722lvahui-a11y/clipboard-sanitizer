#!/bin/bash
# build_macos_app.sh — 将 PyInstaller 产物打包成 macOS .app
# 在 GitHub Actions macos runner 上执行

set -e

EXE_NAME="ClipboardSanitizer"
APP_NAME="${EXE_NAME}_new.app"
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

# 5. 生成爱心图标 — 先用 Python 生成 PNG，再用 iconutil 转 icns
echo "  生成爱心图标..."
python3 clipboard-sanitizer-extension/generate_icons.py 2>/dev/null || python3 -c "
import struct, zlib, os
os.makedirs('icons', exist_ok=True)
def heart(x,y,s):
    cx,cy=x-s/2,y-s*0.42
    v=((cx/(s*0.51))**2+(-cy/(s*0.52))**2-1)**3-(cx/(s*0.51))**2*(-cy/(s*0.52))**3
    if v<=0.05:return(76,175,80,255)
    if abs(v)<0.15:return(76,175,80,180)
    return(0,0,0,0)
def png(s,n):
    raw=b''
    for y in range(s):
        raw+=b'\x00'
        for x in range(s):
            raw+=struct.pack('BBBB',*heart(x,y,s))
    def c(t,d):c2=t+d;return struct.pack('>I',len(d))+c2+struct.pack('>I',zlib.crc32(c2)&0xffffffff)
    with open(n,'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n'+c(b'IHDR',struct.pack('>IIBBBBB',s,s,8,6,0,0,0))+c(b'IDAT',zlib.compress(raw))+c(b'IEND',b''))
for s,n in[(16,'icons/icon16.png'),(48,'icons/icon48.png'),(128,'icons/icon128.png')]:png(s,n)
print('  icons generated')
"

if [ -f "icons/icon128.png" ]; then
    ICONSET="${EXE_NAME}.iconset"
    rm -rf "${ICONSET}"
    mkdir -p "${ICONSET}"
    sips -z 16 16   icons/icon128.png --out "${ICONSET}/icon_16x16.png"      2>/dev/null || true
    sips -z 32 32   icons/icon128.png --out "${ICONSET}/icon_16x16@2x.png"   2>/dev/null || true
    sips -z 32 32   icons/icon128.png --out "${ICONSET}/icon_32x32.png"      2>/dev/null || true
    sips -z 64 64   icons/icon128.png --out "${ICONSET}/icon_32x32@2x.png"   2>/dev/null || true
    sips -z 128 128 icons/icon128.png --out "${ICONSET}/icon_128x128.png"    2>/dev/null || true
    sips -z 256 256 icons/icon128.png --out "${ICONSET}/icon_256x256.png"    2>/dev/null || true
    sips -z 256 256 icons/icon128.png --out "${ICONSET}/icon_128x128@2x.png" 2>/dev/null || true
    sips -z 512 512 icons/icon128.png --out "${ICONSET}/icon_512x512.png"    2>/dev/null || true
    iconutil -c icns "${ICONSET}" -o "${APP_NAME}/Contents/Resources/icon.icns" 2>/dev/null || true
    rm -rf "${ICONSET}"
    if [ -f "${APP_NAME}/Contents/Resources/icon.icns" ]; then
        echo "  ✅ 爱心图标已生成"
    fi
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
    <string>黑毛猪净化器</string>
    <key>CFBundleDisplayName</key>
    <string>黑毛猪净化器</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.1</string>
    <key>CFBundleVersion</key>
    <string>2.1.0</string>
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
echo "双击 ${APP_NAME} 即可启动"
