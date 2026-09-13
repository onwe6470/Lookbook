# Build LookBook for an HONOR / MagicOS phone

The app is a Kivy application. Android does not run `main.py` directly, so
Buildozer and python-for-android package Python, Kivy, the SQLite database code,
and the rest of the project into an installable `.apk`.

## Easiest first build: GitHub Actions

1. Create a new GitHub repository, for example `lookbook`.
2. Upload **the contents of this project folder** to the root of the repository.
   `main.py`, `buildozer.spec`, and `.github/` should all be at repository root.
3. Open the repository on GitHub.
4. Click **Actions**.
5. Open **Build Android APK**.
6. Click **Run workflow**.
7. When the run finishes, open it and download the
   **LookBook-Android-APK** artifact.
8. The downloaded artifact is a ZIP. Extract it; inside is the APK.

The first Android build can take substantially longer than later builds because
Android SDK/NDK and Python packages have to be downloaded and compiled. GitHub's
cache is configured to speed up later builds.

## Put the APK on GitHub for phone download

For the first test, make a GitHub Release manually:

1. In the repository choose **Releases** -> **Draft a new release**.
2. Create a tag such as `v1.1.0`.
3. Give the release a name such as `LookBook 1.1.0`.
4. Drag the generated `.apk` into the release assets area.
5. Publish the release.

You can now open that GitHub Release page on the phone and tap the APK asset.

## Install on MagicOS

When installing an APK downloaded from a browser, Android/MagicOS will normally
ask you to allow that browser or file manager to install apps from an external
source. Enable that permission only for the app you are using to open the APK,
then install LookBook.

Android may also display a warning because the APK did not come from an app
store. This is expected for a private sideloaded application.

## Important: future updates and signing

The GitHub workflow currently makes a **debug-signed APK**, which is ideal for
getting the app onto your phone for the first time.

Android only permits an installed app to be updated by another APK signed with
the same key. A fresh cloud build environment can eventually produce a different
debug key. Before you rely on the app for long-term wardrobe data, switch to a
permanent release signing key and keep that key backed up safely.

Do not commit a private signing key or its password to a public GitHub repository.
GitHub Actions secrets can be used for this later.

## App package

Android package id:

`com.owenjames.lookbook`

The project builds only `arm64-v8a`, appropriate for modern 64-bit Android
phones and smaller than a multi-architecture APK.

## Photo picker

The Android build uses the native system chooser through `androidstorage4kivy`.
This matters because modern Android/MagicOS gallery selections use `content://`
URIs rather than ordinary filesystem paths. The selected image is copied into
app-accessible storage and then resized/stored by LookBook.
