[app]

title = LookBook
package.name = lookbook
package.domain = com.owenjames

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,webp,atlas,txt,json

version = 1.2.0

# androidstorage4kivy is required by main.py for the Android system photo picker.
# Keep Pillow out until the picker build is confirmed. It can be added afterwards.
requirements = python3,kivy,plyer,androidstorage4kivy

orientation = portrait
fullscreen = 0

# Version-matched toolchain that produced the successful APK.
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

# androidstorage4kivy's documented permissions for API 33+ image access.
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE

android.debug_artifact = apk
android.release_artifact = apk

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
