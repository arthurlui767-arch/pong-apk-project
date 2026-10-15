[app]

title = Pong
package.name = pongmobile
package.domain = org.familia
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3, pygame
orientation = landscape
fullscreen = 1

android.api = 35
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

p4a.branch = v2024.01.21
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
