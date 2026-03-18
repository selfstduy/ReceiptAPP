[app]
title = 点收单识别
package.name = receiptapp
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,otf,ttc,json
source.include_patterns = config/**
version = 0.1

# 竖屏（buildozer 正确 key 名为 orientation，不是 android.orientation）
orientation = portrait

android.permissions = CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET,ACCESS_MEDIA_LOCATION

android.api = 33
android.ndk = 25b
android.enable_androidx = True
android.archs = arm64-v8a

requirements = python3,kivy==2.2.1,kivymd==1.1.1,plyer==2.1.0,requests==2.32.5,pillow==12.1.1,pyjnius==1.6.1,tencentcloud-sdk-python==3.1.56,cython==0.29.36

# 将 config 打入 APK，供首次或默认配置
android.add_assets = config/
# Android 资源（如 FileProvider 的 xml）
android.add_src = res/

android.cmake = /usr/bin/cmake

log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
android.accept_sdk_license = True