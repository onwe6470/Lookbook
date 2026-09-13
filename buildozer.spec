[app]

title = LookBook
package.name = lookbook
package.domain = com.owenjames

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,webp,atlas,txt,json

version = 1.1.0

# Android-specific packages are included so the phone's system image chooser
# can safely turn content:// gallery URIs into app-private files.
requirements = python3==3.12.9,hostpython3==3.12.9,kivy,pillow,plyer

orientation = portrait
fullscreen = 0

# Current Buildozer/python-for-android target values (2026).
android.api = 36
android.minapi = 24
android.ndk = 29
android.archs = arm64-v8a
android.accept_sdk_license = True

# The app only needs image access. The system chooser grants access to the
# selected URI; these declarations also cover MediaStore access on recent
# Android versions used by androidstorage4kivy.
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE

android.debug_artifact = apk
android.release_artifact = apk

# Stable branch is adequate for a sideloaded APK.
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
