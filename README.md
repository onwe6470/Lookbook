# LookBook v2

A personal wardrobe/look-book application written in Python with Kivy and SQLite, intended to be packaged as an Android APK for Android/MagicOS phones.

## Main sections

### Looks
Store photos of complete outfits, name them, add custom tags, search/filter them, and track how often and how recently each complete look has been worn.

### Items
Store individual clothing items separately from complete looks.

Each item has:

- a photo
- a custom name
- one or more body-area classifications: **head**, **upper body**, **legs**, **feet**
- optional free-form tags such as `winter`, `summer`, `smart`, `casual`, `work`, etc.
- total wear count
- last-worn date
- full dated wear history

The item library can be filtered by body area or custom tag and sorted by least recently worn.

### Sandbox
The sandbox lets you combine individual items into outfit ideas.

Tap clothing items from the available-item list to add/remove them. Selected items are automatically displayed vertically according to their body-area classification:

1. Head
2. Upper body
3. Legs
4. Feet

For an item tagged for more than one body area, the highest applicable body position is used for its sandbox placement. For example, an item tagged `head` + `upper body` is displayed in the head section.

The combination can be saved as a named **look idea**.

Saved look ideas can be marked as worn. Doing this:

- increments the look idea's wear count
- records the look idea's last-worn date
- increments the wear count of **every individual item in the idea**
- records a dated wear-history entry for every included item

This keeps item statistics accurate without requiring you to mark every garment separately each time you wear an outfit idea.

## Existing-data compatibility

The v2 database adds new tables for items and look ideas without removing the original complete-look tables. An existing v1 `lookbook.db` should therefore be upgraded automatically when v2 is first opened.

## Run on a computer

```bash
python -m pip install -r requirements.txt
python main.py
```

## Android / MagicOS

The project includes `buildozer.spec` and a GitHub Actions workflow.

A common local route on Windows is WSL2 + Buildozer:

```bash
python -m pip install buildozer cython
buildozer android debug
```

The APK is generated under `bin/`.

For GitHub, `.github/workflows/android.yml` can build a debug APK as an Actions artifact.

## Project files

```text
lookbook_app/
├── main.py                 # Kivy UI/application logic
├── database.py             # SQLite data layer
├── lookbook.kv             # Kivy layout
├── requirements.txt
├── buildozer.spec
├── README.md
└── .github/workflows/android.yml
```

## Database additions in v2

- `items`
- `item_body_areas`
- `item_tags`
- `item_wear_history`
- `look_ideas`
- `look_idea_items`
- `look_idea_wear_history`

The original tables for overall looks remain intact.

## Android-ready build

For the HONOR/MagicOS APK workflow, see `ANDROID_BUILD.md`. This version also
uses Android's native shared-storage chooser so selecting gallery photos works
with modern `content://` URIs.
