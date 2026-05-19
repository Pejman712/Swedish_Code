[app]

# Application title
title = Swedish Trainer

# Android package name
package.name = swedishtrainer

# Package domain
package.domain = org.test

# Source code directory
source.dir = .

# Include Python, Kivy, images, CSV, and JSON data files
source.include_exts = py,png,jpg,jpeg,kv,atlas,csv,json

# Include app data files
source.include_patterns = data/*.csv,data/*.json,*.kv

# Exclude build/cache folders
source.exclude_dirs = tests,bin,venv,.venv,__pycache__,.git

# Application version
version = 0.1

# Python/Kivy requirements
requirements = python3,kivy

# App orientation
orientation = portrait

# Do not force fullscreen
fullscreen = 0


#
# Android specific
#

# Android API target
android.api = 35

# Minimum Android version supported
android.minapi = 23

# Android NDK API
android.ndk_api = 23

# Android architecture
android.archs = arm64-v8a

# Use private app storage
android.private_storage = True

# Allow Android auto backup
android.allow_backup = True

# Debug APK output format
android.debug_artifact = apk

# Release output format
android.release_artifact = apk

# Optional: permissions
# For this offline trainer, no permission is needed.
# If you later add online text-to-speech, enable INTERNET:
android.permissions = android.permission.INTERNET


#
# Python-for-Android settings
#

# Default bootstrap for Kivy
p4a.bootstrap = sdl2

# Let python-for-android use default upstream settings
# p4a.branch = master
# p4a.commit = HEAD


#
# iOS specific
# You can leave these unchanged unless building for iOS.
#

ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0

ios.codesign.allowed = false


[buildozer]

# 2 = debug output, useful while fixing build issues
log_level = 2

# Warn if running as root
warn_on_root = 1

# Build output folders
build_dir = ./.buildozer
bin_dir = ./bin