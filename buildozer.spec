[app]

title = LookBook
package.name = lookbook
package.domain = com.owenjames

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,webp,atlas,txt,json

version = 1.1.0

# Keep this simple for the older, stable python-for-android release.
requirements = python3,kivy,pillow,plyer

orientation = portrait
fullscreen = 0

# Conservative Android settings for p4a v2024.01.21
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a

android.accept_sdk_license = True

# Photo access
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE

android.debug_artifact = apk
android.release_artifact = apk

# Pin python-for-android to the older stable release.
# This release uses Python 3.11 by default.
p4a.branch = v2024.01.21


[buildozer]

log_level = 2
warn_on_root = 1
