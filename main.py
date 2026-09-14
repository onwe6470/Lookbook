from __future__ import annotations




import shutil
from datetime import date


import sys

# ------------------------------------------------------------
# Windows desktop compatibility
# ------------------------------------------------------------
# Kivy automatically enables the Windows pen/touch providers.
# They can cause:
# AttributeError: 'WM_PenProvider' object has no attribute 'hwnd'
#
# We don't need pen/multitouch input for LookBook, so disable them
# when running the desktop version on Windows.
if sys.platform == "win32":
    from kivy.config import Config

    Config.remove_option("input", "wm_pen")
    Config.remove_option("input", "wm_touch")

from pathlib import Path
from uuid import uuid4

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import Screen
from kivy.utils import platform

from database import BODY_AREAS, BODY_AREA_ORDER, Item, Look, LookBookDB

try:
    from PIL import Image as PILImage
except Exception:
    PILImage = None

try:
    from plyer import filechooser
except Exception:
    filechooser = None

AndroidChooser = None
AndroidSharedStorage = None
if platform == "android":
    try:
        from androidstorage4kivy import Chooser as AndroidChooser
        from androidstorage4kivy import SharedStorage as AndroidSharedStorage
    except Exception:
        AndroidChooser = None
        AndroidSharedStorage = None


class LookCard(BoxLayout):
    look_id = NumericProperty(0)
    look_name = StringProperty("")
    image_path = StringProperty("")
    detail_text = StringProperty("")


class ItemCard(BoxLayout):
    item_id = NumericProperty(0)
    item_name = StringProperty("")
    image_path = StringProperty("")
    detail_text = StringProperty("")


class LooksScreen(Screen):
    pass


class ItemsScreen(Screen):
    pass


class SandboxScreen(Screen):
    pass


class RootWidget(BoxLayout):
    pass


class LookBookApp(App):
    look_tag_choices = ListProperty(["All tags"])
    item_tag_choices = ListProperty(["All tags"])
    body_area_choices = ListProperty(["All body areas", "head", "upper body", "legs", "feet"])

    selected_look_tag = StringProperty("All tags")
    selected_item_tag = StringProperty("All tags")
    selected_body_area = StringProperty("All body areas")

    look_sort = StringProperty("name")
    item_sort = StringProperty("name")

    def build(self):
        self.title = "LookBook"
        self.data_dir = Path(self.user_data_dir)
        self.image_dir = self.data_dir / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.db = LookBookDB(self.data_dir / "lookbook.db")
        self.sandbox_item_ids: set[int] = set()

        if platform not in ("android", "ios"):
            Window.minimum_width = 840
            Window.minimum_height = 650

        return RootWidget()

    def on_start(self):
        self.refresh_all()

    # ---------- navigation ----------
    def show_screen(self, name: str):
        self.root.ids.manager.current = name
        if name == "sandbox":
            self.refresh_sandbox()

    # ---------- common ----------
    @staticmethod
    def days_since(last_worn: str | None) -> int | None:
        if not last_worn:
            return None
        try:
            return (date.today() - date.fromisoformat(last_worn)).days
        except ValueError:
            return None

    @staticmethod
    def _parse_tags(value: str) -> list[str]:
        seen = set()
        result = []
        for raw in value.split(","):
            tag = raw.strip()
            key = tag.casefold()
            if tag and key not in seen:
                seen.add(key)
                result.append(tag)
        return result

    def refresh_all(self):
        self.refresh_tags()
        self.refresh_looks()
        self.refresh_items()
        self.refresh_sandbox()

    def refresh_tags(self):
        tags = [name for _, name, _ in self.db.list_tags()]
        choices = ["All tags"] + tags
        self.look_tag_choices = choices
        self.item_tag_choices = choices

        if self.selected_look_tag not in choices:
            self.selected_look_tag = "All tags"
        if self.selected_item_tag not in choices:
            self.selected_item_tag = "All tags"

        if self.root:
            self.root.ids.looks_screen.ids.look_tag_spinner.values = choices
            self.root.ids.looks_screen.ids.look_tag_spinner.text = self.selected_look_tag
            self.root.ids.items_screen.ids.item_tag_spinner.values = choices
            self.root.ids.items_screen.ids.item_tag_spinner.text = self.selected_item_tag

    def import_image(self, source_path: str) -> str:
        source = Path(source_path)
        if source.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("Supported formats: JPG, JPEG, PNG and WEBP.")

        destination = self.image_dir / f"{uuid4().hex}.jpg"
        if PILImage is not None:
            with PILImage.open(source) as image:
                image = image.convert("RGB")
                image.thumbnail((1800, 1800))
                image.save(destination, "JPEG", quality=88, optimize=True)
        else:
            destination = destination.with_suffix(source.suffix.lower())
            shutil.copyfile(source, destination)
        return str(destination)

    def _same_file(self, a: str, b: str) -> bool:
        try:
            return Path(a).resolve() == Path(b).resolve()
        except Exception:
            return a == b

    def _delete_image_if_owned(self, image_path: str):
        try:
            path = Path(image_path).resolve()
            if path.parent == self.image_dir.resolve():
                path.unlink(missing_ok=True)
        except Exception:
            pass

    def choose_image(self, callback):
        # Android 10+ gallery files are normally returned as content:// URIs,
        # not ordinary filesystem paths. androidstorage4kivy opens the system
        # chooser and copies the selected image into an app-accessible cache
        # file before handing it back to the rest of the app.
        if platform == "android":
            if AndroidChooser is None or AndroidSharedStorage is None:
                self.show_message(
                    "Android photo picker support is unavailable. "
                    "Rebuild the APK with androidstorage4kivy included."
                )
                return

            self._android_image_callback = callback
            self._android_chooser = AndroidChooser(self._android_image_chosen)
            self._android_chooser.choose_content("image/*")
            return

        chooser = FileChooserListView(
            path=str(Path.home()),
            filters=["*.jpg", "*.jpeg", "*.png", "*.webp"],
            multiselect=False,
        )
        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        select_button = Button(text="Select")
        cancel_button = Button(text="Cancel")
        buttons.add_widget(select_button)
        buttons.add_widget(cancel_button)
        content = BoxLayout(orientation="vertical")
        content.add_widget(chooser)
        content.add_widget(buttons)
        popup = Popup(title="Choose photo", content=content, size_hint=(0.94, 0.9), auto_dismiss=False)

        def select(*_):
            if chooser.selection:
                selected = chooser.selection[0]
                popup.dismiss()
                callback(selected)

        select_button.bind(on_release=select)
        cancel_button.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def _android_image_chosen(self, shared_files):
        callback = getattr(self, "_android_image_callback", None)
        if not shared_files or callback is None:
            return

        try:
            private_path = AndroidSharedStorage().copy_from_shared(shared_files[0])
        except Exception as exc:
            Clock.schedule_once(
                lambda *_: self.show_message(f"Could not read the selected photo:\n{exc}"),
                0,
            )
            return

        if not private_path:
            Clock.schedule_once(
                lambda *_: self.show_message("Could not copy the selected photo into the app."),
                0,
            )
            return

        # Marshal the UI update back onto Kivy's main thread.
        Clock.schedule_once(lambda *_: callback(str(private_path)), 0)

    def show_message(self, message: str):
        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        message_label = Label(
            text=message,
            halign="center",
            valign="middle",
            font_size="14sp",
        )
        # Constrain the text to the label width so long Android error messages
        # wrap instead of running off the side of the phone.
        message_label.bind(
            size=lambda widget, value: setattr(widget, "text_size", value)
        )
        content.add_widget(message_label)
        close = Button(text="OK", size_hint_y=None, height=dp(48))
        content.add_widget(close)
        popup = Popup(title="", content=content, size_hint=(0.90, 0.38), auto_dismiss=False)
        close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    # ---------- overall looks ----------
    def set_look_tag(self, value: str):
        if value in self.look_tag_choices:
            self.selected_look_tag = value
            self.refresh_looks()

    def set_look_sort(self, mode: str):
        self.look_sort = mode
        self.refresh_looks()

    def refresh_looks(self, *_):
        if not self.root:
            return
        screen = self.root.ids.looks_screen
        search = screen.ids.look_search.text.strip()
        tag = None if self.selected_look_tag == "All tags" else self.selected_look_tag
        looks = self.db.list_looks(search, tag, self.look_sort == "oldest")
        grid = screen.ids.look_grid
        grid.clear_widgets()
        if not looks:
            grid.add_widget(Label(text="No overall looks yet.", size_hint_y=None, height=dp(100)))
            return
        for look in looks:
            days = self.days_since(look.last_worn)
            last = "Never" if days is None else ("Today" if days == 0 else f"{days} day(s) ago")
            grid.add_widget(
                LookCard(
                    look_id=look.id,
                    look_name=look.name,
                    image_path=look.image_path,
                    detail_text=f"Worn: {look.wear_count}\nLast worn: {last}\n{', '.join(look.tags) or 'No tags'}",
                )
            )

    def open_add_look(self):
        self.open_look_editor(None)

    def open_edit_look(self, look_id: int):
        self.open_look_editor(self.db.get_look(look_id))

    def open_look_editor(self, look: Look | None):
        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        content.add_widget(Label(text="Edit overall look" if look else "Add overall look", size_hint_y=None, height=dp(38), font_size="21sp", bold=True))
        name_input = TextInput(text=look.name if look else "", hint_text="Look name", multiline=False, size_hint_y=None, height=dp(48))
        tag_input = TextInput(text=", ".join(look.tags) if look else "", hint_text="Tags separated by commas", multiline=False, size_hint_y=None, height=dp(48))
        selected_image = {"path": look.image_path if look else None}
        image_label = Label(text=Path(look.image_path).name if look else "No photo selected", size_hint_y=None, height=dp(36), shorten=True)
        choose_button = Button(text="Choose overall-look photo", size_hint_y=None, height=dp(48))
        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        save_button, cancel_button = Button(text="Save"), Button(text="Cancel")
        actions.add_widget(save_button); actions.add_widget(cancel_button)

        def selected(path):
            if path:
                selected_image["path"] = path
                image_label.text = Path(path).name

        def save(*_):
            name = name_input.text.strip()
            source = selected_image["path"]
            if not name or not source:
                self.show_message("Please enter a name and choose a photo.")
                return
            try:
                stored = look.image_path if look and self._same_file(source, look.image_path) else self.import_image(source)
            except Exception as exc:
                self.show_message(f"Could not import photo:\n{exc}")
                return
            tags = self._parse_tags(tag_input.text)
            if look:
                old = look.image_path
                self.db.update_look(look.id, name, stored, tags)
                if old != stored:
                    self._delete_image_if_owned(old)
            else:
                self.db.add_look(name, stored, tags)
            popup.dismiss(); self.refresh_all()

        choose_button.bind(on_release=lambda *_: self.choose_image(selected))
        save_button.bind(on_release=save)
        cancel_button.bind(on_release=lambda *_: popup.dismiss())
        for widget in (name_input, tag_input, image_label, choose_button): content.add_widget(widget)
        if look:
            worn = Button(text=f"Wore this today  •  {look.wear_count} total", size_hint_y=None, height=dp(48))
            worn.bind(on_release=lambda *_: (popup.dismiss(), self.mark_look_worn(look.id)))
            content.add_widget(worn)
            delete = Button(text="Delete look", size_hint_y=None, height=dp(48))
            delete.bind(on_release=lambda *_: (popup.dismiss(), self.delete_look(look.id)))
            content.add_widget(delete)
        content.add_widget(actions)
        popup = Popup(title="", content=content, size_hint=(0.94, 0.90), auto_dismiss=False)
        popup.open()

    def mark_look_worn(self, look_id: int):
        self.db.mark_look_worn(look_id)
        self.refresh_looks()

    def delete_look(self, look_id: int):
        path = self.db.delete_look(look_id)
        if path:
            self._delete_image_if_owned(path)
        self.refresh_all()

    # ---------- individual items ----------
    def set_item_tag(self, value: str):
        if value in self.item_tag_choices:
            self.selected_item_tag = value
            self.refresh_items()

    def set_body_area(self, value: str):
        if value in self.body_area_choices:
            self.selected_body_area = value
            self.refresh_items()

    def set_item_sort(self, mode: str):
        self.item_sort = mode
        self.refresh_items()

    def refresh_items(self, *_):
        if not self.root:
            return
        screen = self.root.ids.items_screen
        search = screen.ids.item_search.text.strip()
        tag = None if self.selected_item_tag == "All tags" else self.selected_item_tag
        area = None if self.selected_body_area == "All body areas" else self.selected_body_area
        items = self.db.list_items(search, area, tag, self.item_sort == "oldest")
        grid = screen.ids.item_grid
        grid.clear_widgets()
        if not items:
            grid.add_widget(Label(text="No clothing items yet.", size_hint_y=None, height=dp(100)))
            return
        for item in items:
            days = self.days_since(item.last_worn)
            last = "Never" if days is None else ("Today" if days == 0 else f"{days} day(s) ago")
            areas = " + ".join(item.body_areas)
            extra = f" | {', '.join(item.tags)}" if item.tags else ""
            grid.add_widget(
                ItemCard(
                    item_id=item.id,
                    item_name=item.name,
                    image_path=item.image_path,
                    detail_text=f"{areas}{extra}\nWorn: {item.wear_count}  •  Last: {last}",
                )
            )

    def open_add_item(self):
        self.open_item_editor(None)

    def open_edit_item(self, item_id: int):
        self.open_item_editor(self.db.get_item(item_id))

    def open_item_editor(self, item: Item | None):
        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        content.add_widget(Label(text="Edit clothing item" if item else "Add clothing item", size_hint_y=None, height=dp(38), font_size="21sp", bold=True))
        name_input = TextInput(text=item.name if item else "", hint_text="Item name, e.g. Navy jumper", multiline=False, size_hint_y=None, height=dp(48))
        tag_input = TextInput(text=", ".join(item.tags) if item else "", hint_text="Optional tags: winter, work, casual...", multiline=False, size_hint_y=None, height=dp(48))
        content.add_widget(name_input)

        content.add_widget(Label(text="Where is it worn? Select one or more:", size_hint_y=None, height=dp(28), halign="left"))
        checks = {}
        area_row = GridLayout(cols=2, size_hint_y=None, height=dp(100), spacing=dp(4))
        for area in BODY_AREAS:
            line = BoxLayout(size_hint_y=None, height=dp(42))
            cb = CheckBox(active=bool(item and area in item.body_areas), size_hint_x=None, width=dp(45))
            checks[area] = cb
            line.add_widget(cb); line.add_widget(Label(text=area.title(), halign="left"))
            area_row.add_widget(line)
        content.add_widget(area_row)
        content.add_widget(tag_input)

        selected_image = {"path": item.image_path if item else None}
        image_label = Label(text=Path(item.image_path).name if item else "No photo selected", size_hint_y=None, height=dp(36), shorten=True)
        choose_button = Button(text="Choose item photo", size_hint_y=None, height=dp(48))
        content.add_widget(image_label); content.add_widget(choose_button)

        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        save_button, cancel_button = Button(text="Save"), Button(text="Cancel")
        actions.add_widget(save_button); actions.add_widget(cancel_button)

        def selected(path):
            if path:
                selected_image["path"] = path
                image_label.text = Path(path).name

        def save(*_):
            name = name_input.text.strip()
            source = selected_image["path"]
            areas = [area for area, cb in checks.items() if cb.active]
            if not name or not source:
                self.show_message("Please enter an item name and choose a photo.")
                return
            if not areas:
                self.show_message("Select at least one body area: head, upper body, legs or feet.")
                return
            try:
                stored = item.image_path if item and self._same_file(source, item.image_path) else self.import_image(source)
            except Exception as exc:
                self.show_message(f"Could not import photo:\n{exc}")
                return
            tags = self._parse_tags(tag_input.text)
            if item:
                old = item.image_path
                self.db.update_item(item.id, name, stored, areas, tags)
                if old != stored:
                    self._delete_image_if_owned(old)
            else:
                self.db.add_item(name, stored, areas, tags)
            popup.dismiss(); self.refresh_all()

        choose_button.bind(on_release=lambda *_: self.choose_image(selected))
        save_button.bind(on_release=save)
        cancel_button.bind(on_release=lambda *_: popup.dismiss())

        if item:
            worn = Button(text=f"Wore this today  •  {item.wear_count} total", size_hint_y=None, height=dp(48))
            worn.bind(on_release=lambda *_: (popup.dismiss(), self.mark_item_worn(item.id)))
            history = Button(text="Wear history", size_hint_y=None, height=dp(48))
            history.bind(on_release=lambda *_: self.open_item_history(item.id))
            delete = Button(text="Delete item", size_hint_y=None, height=dp(48))
            delete.bind(on_release=lambda *_: (popup.dismiss(), self.delete_item(item.id)))
            content.add_widget(worn); content.add_widget(history); content.add_widget(delete)
        content.add_widget(actions)
        popup = Popup(title="", content=content, size_hint=(0.94, 0.94), auto_dismiss=False)
        popup.open()

    def mark_item_worn(self, item_id: int):
        self.db.mark_item_worn(item_id)
        self.refresh_all()

    def open_item_history(self, item_id: int):
        item = self.db.get_item(item_id)
        if not item:
            return
        history = self.db.item_wear_history(item_id)
        text = "\n".join(history) if history else "This item has not been marked worn yet."
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        content.add_widget(Label(text=f"{item.name}\n\n{text}"))
        close = Button(text="Close", size_hint_y=None, height=dp(48)); content.add_widget(close)
        popup = Popup(title="Item wear history", content=content, size_hint=(0.86, 0.7), auto_dismiss=False)
        close.bind(on_release=lambda *_: popup.dismiss()); popup.open()

    def delete_item(self, item_id: int):
        self.sandbox_item_ids.discard(item_id)
        path = self.db.delete_item(item_id)
        if path:
            self._delete_image_if_owned(path)
        self.refresh_all()

    # ---------- sandbox ----------
    def toggle_sandbox_item(self, item_id: int):
        if item_id in self.sandbox_item_ids:
            self.sandbox_item_ids.remove(item_id)
        else:
            self.sandbox_item_ids.add(item_id)
        self.refresh_sandbox()

    def clear_sandbox(self):
        self.sandbox_item_ids.clear()
        self.refresh_sandbox()

    def load_idea_to_sandbox(self, idea_id: int):
        idea = self.db.get_look_idea(idea_id)
        if not idea:
            self.show_message("Could not find that saved look idea.")
            return
        self.sandbox_item_ids = set(idea.item_ids)
        self.refresh_sandbox()

    def refresh_sandbox(self):
        if not self.root:
            return
        screen = self.root.ids.sandbox_screen
        available = screen.ids.sandbox_available
        available.clear_widgets()

        all_items = self.db.list_items()
        for item in all_items:
            selected = item.id in self.sandbox_item_ids
            button = Button(
                text=("✓ " if selected else "+ ") + item.name + "\n" + " / ".join(item.body_areas),
                size_hint_y=None,
                height=dp(58),
            )
            button.bind(on_release=lambda _, item_id=item.id: self.toggle_sandbox_item(item_id))
            available.add_widget(button)

        selected_items = [self.db.get_item(i) for i in self.sandbox_item_ids]
        selected_items = [i for i in selected_items if i is not None]

        for area in BODY_AREAS:
            zone = screen.ids[f"sandbox_{area.replace(' ', '_')}"]
            zone.clear_widgets()
            area_items = [i for i in selected_items if self.primary_area(i) == area]
            if not area_items:
                zone.add_widget(Label(text=f"{area.title()}\n—", size_hint_y=None, height=dp(65)))
                continue
            zone.add_widget(Label(text=area.title(), size_hint_y=None, height=dp(26), bold=True))
            for item in sorted(area_items, key=lambda x: x.name.casefold()):
                row = BoxLayout(size_hint_y=None, height=dp(120), spacing=dp(6))
                row.add_widget(Image(source=item.image_path, allow_stretch=True, keep_ratio=True))
                remove = Button(text=f"{item.name}\nRemove", size_hint_x=0.7)
                remove.bind(on_release=lambda _, item_id=item.id: self.toggle_sandbox_item(item_id))
                row.add_widget(remove)
                zone.add_widget(row)

        ideas = screen.ids.saved_ideas
        ideas.clear_widgets()
        for idea in self.db.list_look_ideas():
            item_names = []
            for item_id in idea.item_ids:
                item = self.db.get_item(item_id)
                if item:
                    item_names.append(item.name)
            days = self.days_since(idea.last_worn)
            last = "Never" if days is None else ("Today" if days == 0 else f"{days} day(s) ago")
            card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(126),
                spacing=dp(5),
                padding=dp(6),
            )
            label = Label(
                text=f"{idea.name}\n{', '.join(item_names)}\nWorn {idea.wear_count} • Last: {last}",
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(72),
                font_size="12sp",
            )
            label.bind(size=lambda widget, value: setattr(widget, "text_size", value))

            actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(5))
            load = Button(text="Load")
            load.bind(on_release=lambda _, idea_id=idea.id: self.load_idea_to_sandbox(idea_id))
            wore = Button(text="Wore it")
            wore.bind(on_release=lambda _, idea_id=idea.id: self.mark_idea_worn(idea_id))
            delete = Button(text="Delete")
            delete.bind(on_release=lambda _, idea_id=idea.id: self.delete_idea(idea_id))
            actions.add_widget(load); actions.add_widget(wore); actions.add_widget(delete)
            card.add_widget(label); card.add_widget(actions)
            ideas.add_widget(card)

    @staticmethod
    def primary_area(item: Item) -> str:
        if not item.body_areas:
            return "upper body"
        return min(item.body_areas, key=lambda area: BODY_AREA_ORDER.get(area, 99))

    def save_sandbox_idea(self):
        if not self.sandbox_item_ids:
            self.show_message("Add at least one clothing item to the sandbox first.")
            return
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        name_input = TextInput(hint_text="Look idea name", multiline=False, size_hint_y=None, height=dp(48))
        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        save, cancel = Button(text="Save idea"), Button(text="Cancel")
        buttons.add_widget(save); buttons.add_widget(cancel)
        content.add_widget(Label(text="Save this combination as a look idea", size_hint_y=None, height=dp(36)))
        content.add_widget(name_input); content.add_widget(buttons)
        popup = Popup(title="", content=content, size_hint=(0.86, 0.34), auto_dismiss=False)

        def do_save(*_):
            name = name_input.text.strip()
            if not name:
                self.show_message("Give the look idea a name.")
                return
            self.db.save_look_idea(name, sorted(self.sandbox_item_ids))
            popup.dismiss(); self.clear_sandbox(); self.refresh_sandbox()

        save.bind(on_release=do_save); cancel.bind(on_release=lambda *_: popup.dismiss()); popup.open()

    def mark_idea_worn(self, idea_id: int):
        self.db.mark_look_idea_worn(idea_id)
        self.refresh_all()

    def delete_idea(self, idea_id: int):
        self.db.delete_look_idea(idea_id)
        self.refresh_sandbox()


if __name__ == "__main__":
    LookBookApp().run()
