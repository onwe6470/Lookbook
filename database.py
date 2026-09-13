from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

BODY_AREAS = ("head", "upper body", "legs", "feet")
BODY_AREA_ORDER = {name: i for i, name in enumerate(BODY_AREAS)}


@dataclass
class Look:
    id: int
    name: str
    image_path: str
    wear_count: int
    last_worn: str | None
    tags: list[str]


@dataclass
class Item:
    id: int
    name: str
    image_path: str
    wear_count: int
    last_worn: str | None
    body_areas: list[str]
    tags: list[str]


@dataclass
class LookIdea:
    id: int
    name: str
    created_on: str
    wear_count: int
    last_worn: str | None
    item_ids: list[int]


class LookBookDB:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialise(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS looks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    wear_count INTEGER NOT NULL DEFAULT 0,
                    last_worn TEXT
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE
                );

                CREATE TABLE IF NOT EXISTS look_tags (
                    look_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (look_id, tag_id),
                    FOREIGN KEY (look_id) REFERENCES looks(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS wear_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    look_id INTEGER NOT NULL,
                    worn_on TEXT NOT NULL,
                    FOREIGN KEY (look_id) REFERENCES looks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    wear_count INTEGER NOT NULL DEFAULT 0,
                    last_worn TEXT
                );

                CREATE TABLE IF NOT EXISTS item_body_areas (
                    item_id INTEGER NOT NULL,
                    body_area TEXT NOT NULL,
                    PRIMARY KEY (item_id, body_area),
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS item_tags (
                    item_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (item_id, tag_id),
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS item_wear_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    worn_on TEXT NOT NULL,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS look_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_on TEXT NOT NULL,
                    wear_count INTEGER NOT NULL DEFAULT 0,
                    last_worn TEXT
                );

                CREATE TABLE IF NOT EXISTS look_idea_items (
                    look_idea_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    PRIMARY KEY (look_idea_id, item_id),
                    FOREIGN KEY (look_idea_id) REFERENCES look_ideas(id) ON DELETE CASCADE,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS look_idea_wear_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    look_idea_id INTEGER NOT NULL,
                    worn_on TEXT NOT NULL,
                    FOREIGN KEY (look_idea_id) REFERENCES look_ideas(id) ON DELETE CASCADE
                );
                """
            )

    # ------------------------------
    # Shared tag helpers
    # ------------------------------
    def _ensure_tag(self, conn: sqlite3.Connection, tag: str) -> int:
        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (tag,)
        ).fetchone()
        return int(row["id"])

    def list_tags(self) -> list[tuple[int, str, int]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.name,
                       COUNT(DISTINCT lt.look_id) + COUNT(DISTINCT it.item_id) AS use_count
                FROM tags t
                LEFT JOIN look_tags lt ON lt.tag_id = t.id
                LEFT JOIN item_tags it ON it.tag_id = t.id
                GROUP BY t.id
                ORDER BY t.name COLLATE NOCASE
                """
            ).fetchall()
        return [(r["id"], r["name"], r["use_count"]) for r in rows]

    def add_tag(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))

    def delete_tag(self, tag_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))

    # ------------------------------
    # Overall looks
    # ------------------------------
    def _look_tags(self, conn: sqlite3.Connection, look_id: int) -> list[str]:
        rows = conn.execute(
            """
            SELECT t.name
            FROM tags t
            JOIN look_tags lt ON lt.tag_id = t.id
            WHERE lt.look_id = ?
            ORDER BY t.name COLLATE NOCASE
            """,
            (look_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def _set_look_tags(self, conn, look_id: int, tags: Iterable[str]) -> None:
        conn.execute("DELETE FROM look_tags WHERE look_id = ?", (look_id,))
        seen = set()
        for raw in tags:
            tag = raw.strip()
            key = tag.casefold()
            if not tag or key in seen:
                continue
            seen.add(key)
            tag_id = self._ensure_tag(conn, tag)
            conn.execute(
                "INSERT OR IGNORE INTO look_tags(look_id, tag_id) VALUES (?, ?)",
                (look_id, tag_id),
            )

    def list_looks(self, search="", tag: str | None = None, sort_oldest_first=False):
        query = "SELECT * FROM looks WHERE 1=1"
        params: list[object] = []
        if search:
            query += " AND name LIKE ?"
            params.append(f"%{search}%")
        if tag:
            query += """
                AND EXISTS (
                    SELECT 1 FROM look_tags lt
                    JOIN tags t ON t.id = lt.tag_id
                    WHERE lt.look_id = looks.id AND t.name = ? COLLATE NOCASE
                )
            """
            params.append(tag)
        if sort_oldest_first:
            query += " ORDER BY CASE WHEN last_worn IS NULL THEN 0 ELSE 1 END, last_worn ASC, name COLLATE NOCASE"
        else:
            query += " ORDER BY name COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                Look(r["id"], r["name"], r["image_path"], r["wear_count"], r["last_worn"], self._look_tags(conn, r["id"]))
                for r in rows
            ]

    def get_look(self, look_id: int) -> Look | None:
        with self.connect() as conn:
            r = conn.execute("SELECT * FROM looks WHERE id = ?", (look_id,)).fetchone()
            if not r:
                return None
            return Look(r["id"], r["name"], r["image_path"], r["wear_count"], r["last_worn"], self._look_tags(conn, look_id))

    def add_look(self, name: str, image_path: str, tags: Iterable[str]) -> int:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO looks(name, image_path) VALUES (?, ?)", (name.strip(), image_path))
            look_id = int(cur.lastrowid)
            self._set_look_tags(conn, look_id, tags)
            return look_id

    def update_look(self, look_id: int, name: str, image_path: str, tags: Iterable[str]) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE looks SET name=?, image_path=? WHERE id=?", (name.strip(), image_path, look_id))
            self._set_look_tags(conn, look_id, tags)

    def mark_look_worn(self, look_id: int, worn_on: date | None = None) -> None:
        value = (worn_on or date.today()).isoformat()
        with self.connect() as conn:
            conn.execute("UPDATE looks SET wear_count=wear_count+1, last_worn=? WHERE id=?", (value, look_id))
            conn.execute("INSERT INTO wear_history(look_id, worn_on) VALUES (?, ?)", (look_id, value))

    def delete_look(self, look_id: int) -> str | None:
        look = self.get_look(look_id)
        if not look:
            return None
        with self.connect() as conn:
            conn.execute("DELETE FROM looks WHERE id=?", (look_id,))
        return look.image_path

    # ------------------------------
    # Individual clothing items
    # ------------------------------
    def _item_body_areas(self, conn, item_id: int) -> list[str]:
        rows = conn.execute("SELECT body_area FROM item_body_areas WHERE item_id=?", (item_id,)).fetchall()
        values = [r["body_area"] for r in rows]
        return sorted(values, key=lambda v: BODY_AREA_ORDER.get(v, 99))

    def _item_tags(self, conn, item_id: int) -> list[str]:
        rows = conn.execute(
            """
            SELECT t.name FROM tags t
            JOIN item_tags it ON it.tag_id=t.id
            WHERE it.item_id=?
            ORDER BY t.name COLLATE NOCASE
            """,
            (item_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def _set_item_body_areas(self, conn, item_id: int, body_areas: Iterable[str]) -> None:
        conn.execute("DELETE FROM item_body_areas WHERE item_id=?", (item_id,))
        seen = set()
        for raw in body_areas:
            area = raw.strip().casefold()
            if area in BODY_AREAS and area not in seen:
                seen.add(area)
                conn.execute("INSERT INTO item_body_areas(item_id, body_area) VALUES (?, ?)", (item_id, area))

    def _set_item_tags(self, conn, item_id: int, tags: Iterable[str]) -> None:
        conn.execute("DELETE FROM item_tags WHERE item_id=?", (item_id,))
        seen = set()
        for raw in tags:
            tag = raw.strip()
            key = tag.casefold()
            if not tag or key in seen:
                continue
            seen.add(key)
            tag_id = self._ensure_tag(conn, tag)
            conn.execute("INSERT OR IGNORE INTO item_tags(item_id, tag_id) VALUES (?, ?)", (item_id, tag_id))

    def list_items(
        self,
        search: str = "",
        body_area: str | None = None,
        tag: str | None = None,
        sort_oldest_first: bool = False,
    ) -> list[Item]:
        query = "SELECT * FROM items WHERE 1=1"
        params: list[object] = []
        if search:
            query += " AND name LIKE ?"
            params.append(f"%{search}%")
        if body_area:
            query += " AND EXISTS (SELECT 1 FROM item_body_areas iba WHERE iba.item_id=items.id AND iba.body_area=?)"
            params.append(body_area)
        if tag:
            query += """
                AND EXISTS (
                    SELECT 1 FROM item_tags it
                    JOIN tags t ON t.id=it.tag_id
                    WHERE it.item_id=items.id AND t.name=? COLLATE NOCASE
                )
            """
            params.append(tag)
        if sort_oldest_first:
            query += " ORDER BY CASE WHEN last_worn IS NULL THEN 0 ELSE 1 END, last_worn ASC, name COLLATE NOCASE"
        else:
            query += " ORDER BY name COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                Item(
                    r["id"], r["name"], r["image_path"], r["wear_count"], r["last_worn"],
                    self._item_body_areas(conn, r["id"]), self._item_tags(conn, r["id"]),
                )
                for r in rows
            ]

    def get_item(self, item_id: int) -> Item | None:
        with self.connect() as conn:
            r = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            if not r:
                return None
            return Item(
                r["id"], r["name"], r["image_path"], r["wear_count"], r["last_worn"],
                self._item_body_areas(conn, item_id), self._item_tags(conn, item_id),
            )

    def add_item(self, name: str, image_path: str, body_areas: Iterable[str], tags: Iterable[str]) -> int:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO items(name, image_path) VALUES (?, ?)", (name.strip(), image_path))
            item_id = int(cur.lastrowid)
            self._set_item_body_areas(conn, item_id, body_areas)
            self._set_item_tags(conn, item_id, tags)
            return item_id

    def update_item(self, item_id: int, name: str, image_path: str, body_areas: Iterable[str], tags: Iterable[str]) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE items SET name=?, image_path=? WHERE id=?", (name.strip(), image_path, item_id))
            self._set_item_body_areas(conn, item_id, body_areas)
            self._set_item_tags(conn, item_id, tags)

    def mark_item_worn(self, item_id: int, worn_on: date | None = None) -> None:
        value = (worn_on or date.today()).isoformat()
        with self.connect() as conn:
            conn.execute("UPDATE items SET wear_count=wear_count+1, last_worn=? WHERE id=?", (value, item_id))
            conn.execute("INSERT INTO item_wear_history(item_id, worn_on) VALUES (?, ?)", (item_id, value))

    def item_wear_history(self, item_id: int) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT worn_on FROM item_wear_history WHERE item_id=? ORDER BY worn_on DESC, id DESC",
                (item_id,),
            ).fetchall()
        return [r["worn_on"] for r in rows]

    def delete_item(self, item_id: int) -> str | None:
        item = self.get_item(item_id)
        if not item:
            return None
        with self.connect() as conn:
            conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        return item.image_path

    # ------------------------------
    # Sandbox look ideas
    # ------------------------------
    def save_look_idea(self, name: str, item_ids: Iterable[int]) -> int:
        item_ids = list(dict.fromkeys(int(i) for i in item_ids))
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO look_ideas(name, created_on) VALUES (?, ?)",
                (name.strip(), date.today().isoformat()),
            )
            idea_id = int(cur.lastrowid)
            for item_id in item_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO look_idea_items(look_idea_id, item_id) VALUES (?, ?)",
                    (idea_id, item_id),
                )
            return idea_id

    def list_look_ideas(self) -> list[LookIdea]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM look_ideas ORDER BY created_on DESC, id DESC").fetchall()
            result = []
            for r in rows:
                item_rows = conn.execute(
                    "SELECT item_id FROM look_idea_items WHERE look_idea_id=?",
                    (r["id"],),
                ).fetchall()
                result.append(
                    LookIdea(
                        r["id"], r["name"], r["created_on"], r["wear_count"], r["last_worn"],
                        [x["item_id"] for x in item_rows],
                    )
                )
            return result

    def get_look_idea(self, idea_id: int) -> LookIdea | None:
        with self.connect() as conn:
            r = conn.execute("SELECT * FROM look_ideas WHERE id=?", (idea_id,)).fetchone()
            if not r:
                return None
            item_rows = conn.execute("SELECT item_id FROM look_idea_items WHERE look_idea_id=?", (idea_id,)).fetchall()
            return LookIdea(
                r["id"], r["name"], r["created_on"], r["wear_count"], r["last_worn"],
                [x["item_id"] for x in item_rows],
            )

    def mark_look_idea_worn(self, idea_id: int, worn_on: date | None = None) -> None:
        value = (worn_on or date.today()).isoformat()
        idea = self.get_look_idea(idea_id)
        if not idea:
            return
        with self.connect() as conn:
            conn.execute("UPDATE look_ideas SET wear_count=wear_count+1, last_worn=? WHERE id=?", (value, idea_id))
            conn.execute("INSERT INTO look_idea_wear_history(look_idea_id, worn_on) VALUES (?, ?)", (idea_id, value))
            for item_id in idea.item_ids:
                conn.execute("UPDATE items SET wear_count=wear_count+1, last_worn=? WHERE id=?", (value, item_id))
                conn.execute("INSERT INTO item_wear_history(item_id, worn_on) VALUES (?, ?)", (item_id, value))

    def delete_look_idea(self, idea_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM look_ideas WHERE id=?", (idea_id,))
