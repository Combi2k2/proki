"""The media library (services/media.py): the dev's pictures and sounds, yours, and the pools."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from proki import settings
from proki.services.media import Library


def kinds(library):
    """Every key in the library, and its kind."""
    return {m["key"]: m["kind"] for m in library.get()[0]}


@pytest.fixture
def library(tmp_path):
    return Library(sqlite3.connect(":memory:"), settings.ASSETS_DIR, tmp_path / "media", pools=["questions"])  # a new one


def test_a_new_library_starts_with_the_devs_files(library, tmp_path):
    found = kinds(library)
    assert found["bugcat/sad"] == "image" and found["alarm-clock"] == "sound"
    assert library.draw(["alarm-clock"]) == str(tmp_path / "media/alarm-clock.mp3")
    assert library.draw([]) is None and library.draw(["nothing"]) is None
    assert library.pools() == {"questions": ["bugcat/what", "bugcat/confused"]}  # the dev's (emojis.json)


def test_get_gives_a_kind_a_page_or_keys(library):
    sounds, total = library.get("sound")
    assert [s["key"] for s in sounds] == ["alarm-clock"] and total == 1 and sounds[0]["added_by"] == "dev"
    page, total = library.get("image", offset=2, limit=3)
    assert len(page) == 3 and total == library.get("image", limit=1)[1] == len(kinds(library)) - 1  # all but the sound
    found, total = library.get(keys=["bugcat/what", "nothing", "alarm-clock"])
    assert [f["key"] for f in found] == ["bugcat/what", "alarm-clock"] and total == 2  # in their order


def test_yours_come_in_as_a_copy(library, tmp_path):
    mine = tmp_path / "Cat.GIF"
    mine.write_bytes((settings.ASSETS_DIR / "media/bugcat/sad.gif").read_bytes())
    key = library.add(mine)
    assert key.startswith("yours/") and library.add(mine) == key  # the same file: kept once
    first = library.get("image", limit=1)[0][0]
    assert first["key"] == key and first["added_by"] == "you" and first["file"].startswith(str(tmp_path / "media/yours"))
    with pytest.raises(ValueError, match="picture or a sound"):
        library.add(tmp_path / "notes.txt")


def test_a_deleted_one_is_gone_a_week_later_and_stays_gone(library, tmp_path):
    copy = tmp_path / "media/bugcat/sad.gif"
    with pytest.raises(ValueError, match="still used"):
        library.remove("bugcat/sad", used={"bugcat/sad"})
    library.remove("bugcat/sad", used=set())
    assert "bugcat/sad" not in kinds(library) and library.draw(["bugcat/sad"]) is None and copy.exists()
    library = Library(library.db, settings.ASSETS_DIR, tmp_path / "media")  # the next start: not copied in again
    assert "bugcat/sad" not in kinds(library)

    week_ago = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    library.db.execute("UPDATE media SET deleted_at = ? WHERE key = 'bugcat/sad'", (week_ago,))
    library.purge()
    assert not copy.exists() and not library.db.execute("SELECT 1 FROM media WHERE key = 'bugcat/sad'").fetchone()
    assert "bugcat/sad" not in kinds(Library(library.db, settings.ASSETS_DIR, tmp_path / "media"))


def test_a_name_is_what_you_see_and_its_key_stays(library, tmp_path):
    mine = tmp_path / "Gong.mp3"
    mine.write_bytes((settings.ASSETS_DIR / "sounds/alarm-clock.mp3").read_bytes() + b"gong")
    key = library.add(mine)
    library.set_pool("questions", [key])
    assert library.get(keys=[key])[0][0]["name"] == "Gong"  # the file's name
    library.rename(key, "  temple gong ")
    assert library.get(keys=[key])[0][0]["name"] == "temple gong" and library.get_pool("questions") == [key]
    assert library.get(keys=["alarm-clock"])[0][0]["name"] == "alarm-clock"  # the dev's: its key
    library.remove(key, used=set())
    assert library.add(mine) == key and library.get(keys=[key])[0][0]["name"] == "temple gong"  # back as it was
    for bad, problem in [("nothing", "no media"), (key, "a line of text")]:
        with pytest.raises(ValueError, match=problem):
            library.rename(bad, "" if bad == key else "x")


def test_one_of_yours_added_again_comes_back(library, tmp_path):
    mine = tmp_path / "mine.png"
    mine.write_bytes((settings.ASSETS_DIR / "media/bugcat/stare_luffy.png").read_bytes())
    key = library.add(mine)
    library.remove(key, used=set())
    assert library.add(mine) == key and key in kinds(library)


def test_a_pool_is_yours_to_set(library):
    library.set_pool("questions", ["bugcat/what", "bugcat/hi"])
    library = Library(library.db, settings.ASSETS_DIR, library.folder)  # the next start: yours stays
    assert library.get_pool("questions") == ["bugcat/what", "bugcat/hi"]
    with pytest.raises(ValueError, match="no media"):
        library.set_pool("questions", ["nothing"])


def test_picks_are_kept_by_an_id_and_the_devs_come_in_once(library):
    assert library.get_picks("focus_session.away.been_away") == ["bugcat/what", "alarm-clock"]  # the dev's (emojis.json): the away poke's
    library.set_picks("mine", ["bugcat/sad", "alarm-clock"])
    assert library.get_picks("mine") == ["bugcat/sad", "alarm-clock"] and library.get_picks("nobody") == []
    assert library.draw(library.get_picks("mine"), "sound").endswith("alarm-clock.mp3")
    with pytest.raises(ValueError, match="no media"):
        library.set_picks("mine", ["nothing"])
    library.set_picks("focus_session.away.been_away", [])
    library = Library(library.db, settings.ASSETS_DIR, library.folder)  # the next start: not taken again
    assert library.get_picks("focus_session.away.been_away") == []
