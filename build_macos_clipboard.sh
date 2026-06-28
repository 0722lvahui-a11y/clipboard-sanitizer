#!/bin/bash
# build_macos_clipboard.sh — 剪贴板历史 macOS .app 打包
set -e

EXE_NAME="ClipboardHistory"
APP_NAME="${EXE_NAME}.app"
DIST_DIR="dist"

echo "=== 创建 .app 捆绑包 (剪贴板历史) ==="
rm -rf "${APP_NAME}"
mkdir -p "${APP_NAME}/Contents/MacOS"
mkdir -p "${APP_NAME}/Contents/Resources"

cp "${DIST_DIR}/${EXE_NAME}" "${APP_NAME}/Contents/MacOS/${EXE_NAME}"
chmod +x "${APP_NAME}/Contents/MacOS/${EXE_NAME}"

# 背景图
if [ -f "background.png" ]; then
    cp "background.png" "${APP_NAME}/Contents/Resources/"
    echo "  ✅ 已包含背景图"
fi

# 图标（爱心粉色）
echo "  生成图标..."
python3 -c "
import struct, zlib, os
os.makedirs('icns_tmp', exist_ok=True)

def px(x,y,s):
    cx,cy=x/s,y/s
    m,r=0.08,0.15
    if cx<m or cx>1-m or cy<m or cy>1-m: return (0,0,0,0)
    # 粉色底
    R,G,B=0xE8,0xB4,0xB8
    # 爱心形状
    hx,hy=cx-0.5,cy-0.45
    v=(hx/0.22)**2+(hy/0.20)**2
    if v<1 and abs(hx)<0.22 and hy>-0.15: R,G,B=255,255,255
    return (R,G,B,255)

def png(sz, out):
    raw=b''
    for y in range(sz):
        raw+=b'\x00'
        for x in range(sz): raw+=struct.pack('BBBB',*px(x,y,sz))
    def ck(t,d):
        c=t+d; return struct.pack('>I',len(d))+c+struct.pack('>I',zlib.crc32(c)&0xffffffff)
    with open(out,'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(ck(b'IHDR',struct.pack('>IIBBBBB',sz,sz,8,6,0,0,0)))
        f.write(ck(b'IDAT',zlib.compress(raw)))
        f.write(ck(b'IEND',b''))

for sz,fn in [(16,'icns_tmp/icon16.png'),(48,'icns_tmp/icon48.png'),(128,'icns_tmp/icon128.png')]:
    png(sz,fn)
print('  ✓')
"

if [ -f "icns_tmp/icon128.png" ]; then
    ICS="${EXE_NAME}.iconset"
    rm -rf "${ICS}"; mkdir -p "${ICS}"
    sips -z 16 16   icns_tmp/icon128.png --out "${ICS}/icon_16x16.png"      2>/dev/null || true
    sips -z 32 32   icns_tmp/icon128.png --out "${ICS}/icon_16x16@2x.png"   2>/dev/null || true
    sips -z 32 32   icns_tmp/icon128.png --out "${ICS}/icon_32x32.png"      2>/dev/null || true
    sips -z 64 64   icns_tmp/icon128.png --out "${ICS}/icon_32x32@2x.png"   2>/dev/null || true
    sips -z 128 128 icns_tmp/icon128.png --out "${ICS}/icon_128x128.png"    2>/dev/null || true
    sips -z 256 256 icns_tmp/icon128.png --out "${ICS}/icon_256x256.png"    2>/dev/null || true
    sips -z 256 256 icns_tmp/icon128.png --out "${ICS}/icon_128x128@2x.png" 2>/dev/null || true
    sips -z 512 512 icns_tmp/icon128.png --out "${ICS}/icon_512x512.png"    2>/dev/null || true
    iconutil -c icns "${ICS}" -o "${APP_NAME}/Contents/Resources/icon.icns" 2>/dev/null || true
    rm -rf "${ICS}"
    [ -f "${APP_NAME}/Contents/Resources/icon.icns" ] && echo "  ✅ 图标已生成"
fi
rm -rf icns_tmp

# Info.plist
cat > "${APP_NAME}/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>zh_CN</string>
    <key>CFBundleExecutable</key>
    <string>ClipboardHistory</string>
    <key>CFBundleIdentifier</key>
    <string>com.clipboard.history</string>
    <key>CFBundleName</key>
    <string>剪贴板历史</string>
    <key>CFBundleDisplayName</key>
    <string>剪贴板历史</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
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
echo "  ${APP_NAME}  ($(du -sh "${APP_NAME}" | cut -f1))"
