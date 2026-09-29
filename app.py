"""
The Road from Bree to Moria — an atmospheric Middle-earth portal that presents
two web challenges as connected destinations in one world.

  /                 The overworld map. Click a location to travel.
  /bree             The Warden's Gate — approach (sets a guest token cookie).
  /gate             The Warden's Gate — broken access control (forgeable cookie).
  /moria            The Doors of Durin — approach the Council archive.
  /council/gate     The Doors — word challenge; issues a session + a scroll.
  /council/scroll/<id>  A sealed scroll (IDOR — no owner check).

Scope note: this is the WEB layer only. Nothing here concerns SSH, the SUID
overflow, the reverse-engineering binary, or the network service — those live
elsewhere and are out of scope. The two vulnerabilities below (a forgeable,
unsigned `role` cookie, and an IDOR on scroll ids) are INTENTIONAL and graded:
their routes, cookie/field/session names, and logic must not change.

Runs locally with `python app.py`; on Heroku via gunicorn (see Procfile).
"""
import os
import sqlite3

from flask import (
    Flask, render_template, abort, request, redirect, url_for, session,
    make_response,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SEG4_SECRET_KEY", os.urandom(24))

# ---------------------------------------------------------------------------
# Diegetic content for the two map destinations. Purely in-world — no real
# names, no "segment", no technical/CTF vocabulary reaches the player.
# ---------------------------------------------------------------------------

LOCATIONS = {
    "bree": {
        "slug": "bree",
        "place": "Bree",
        "sub": "The Warden's Gate",
        "accent": "rust",
        "epigraph": "“None pass the gate without the Warden's leave.”",
        "lore": [
            "At the muddy crossroads east of the Shire, the village of Bree "
            "keeps its wall against the wild. A single gate lets travellers "
            "through, and a single Warden decides who is worthy.",
            "He is an old soldier, and a tired one. He does not question a "
            "face he has waved past before — he trusts the token you "
            "carry, and little else. Show him the right mark of office and "
            "the gate will open without a second glance.",
        ],
        "nudge": "The Warden trusts something you are already carrying — "
                 "if only you would look at it closely.",
        "enter_endpoint": "warden_gate",
        "enter_label": "Approach the Warden's Gate",
    },
    "moria": {
        "slug": "moria",
        "place": "Moria",
        "sub": "The Doors of Durin",
        "accent": "gold",
        "epigraph": "“Speak, friend, and enter.”",
        "lore": [
            "Under the shadow of the Misty Mountains stand the West-gate of "
            "the Dwarrowdelf — the Doors of Durin, invisible until the "
            "moon and the right word wake the silver lines of their making.",
            "Beyond them lies the Council's archive: a hall of sealed scrolls, "
            "each set down under the name of the one who lodged it. Pass the "
            "doors and the archivist will hand you your own scroll — "
            "though the archive is old, and its keepers were never careful "
            "about which hands reach for which record.",
        ],
        "nudge": "Once inside, the scrolls are numbered in a single long "
                 "sequence — and curiosity is no crime.",
        "enter_endpoint": "council_gate",
        "enter_label": "Approach the Doors of Durin",
    },
}


@app.route("/")
def map_home():
    return render_template("map.html", locations=LOCATIONS)


@app.route("/bree")
def bree():
    # Hand the traveller a plain guest token, so there is something to find
    # (and to reconsider) in their own browser. This IS the surface.
    loc = LOCATIONS["bree"]
    resp = make_response(render_template("location.html", loc=loc,
                                         locations=LOCATIONS))
    if request.cookies.get("role") is None:
        resp.set_cookie("role", "guest")
    return resp


@app.route("/moria")
def moria():
    return render_template("location.html", loc=LOCATIONS["moria"],
                           locations=LOCATIONS)


# ---------------------------------------------------------------------------
# LIVE CHALLENGE 1 — The Warden's Gate. Broken access control: authorisation
# trusts a client-controlled, unsigned `role` cookie. Forge role=warden to
# pass. Logic and cookie name are the graded surface — do not change.
# ---------------------------------------------------------------------------

@app.route("/gate")
def warden_gate():
    passed = request.cookies.get("role", "guest") == "warden"
    return render_template("warden.html", passed=passed)


# ---------------------------------------------------------------------------
# LIVE CHALLENGE 2 — The Doors of Durin / Council archive. Insecure Direct
# Object Reference: /council/scroll/<id> checks that a session exists but
# never that the scroll belongs to the session's owner. Scroll id=1 belongs
# to "gandalf" and holds the flag. Routes/fields/session key are graded.
# ---------------------------------------------------------------------------

COUNCIL_DB_PATH = os.path.join(os.path.dirname(__file__), "scrolls.db")
COUNCIL_FLAG = os.environ.get("SEG4_FLAG", "FLAG{Speak_Friend_And_Enter}")


def derive_word(name: str) -> str:
    """Opaque credential check. Must stay byte-identical to the source binary."""
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    h ^= 0xDEADBEEF
    return format(h & 0xFFFFFFFF, "08X")


def init_council_db():
    conn = sqlite3.connect(COUNCIL_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS scrolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            content TEXT NOT NULL
        )"""
    )
    row = conn.execute("SELECT COUNT(*) FROM scrolls WHERE id = 1").fetchone()
    if row[0] == 0:
        conn.execute(
            "INSERT INTO scrolls (id, owner, content) VALUES (1, 'gandalf', ?)",
            (f"The White Council's sealed record -- {COUNCIL_FLAG}",),
        )
    conn.commit()
    conn.close()


@app.route("/council/gate", methods=["GET", "POST"])
def council_gate():
    if request.method == "POST":
        name = request.form.get("name", "")
        word = request.form.get("word", "")
        if name and word and word.strip().upper() == derive_word(name):
            session["council_passed"] = True
            session["council_name"] = name
            conn = sqlite3.connect(COUNCIL_DB_PATH)
            cur = conn.execute(
                "INSERT INTO scrolls (owner, content) VALUES (?, ?)",
                (name, f"A traveller's scroll, sealed by {name}."),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            return redirect(url_for("council_scroll", scroll_id=new_id))
        return render_template("council/gate.html",
                               error="The doors remain shut.")
    return render_template("council/gate.html")


@app.route("/council/scroll/<int:scroll_id>")
def council_scroll(scroll_id):
    # Authentication (did you pass the doors?) but NO authorization (is this
    # scroll yours?). The missing owner comparison is the intentional IDOR.
    if not session.get("council_passed"):
        return redirect(url_for("council_gate"))
    conn = sqlite3.connect(COUNCIL_DB_PATH)
    row = conn.execute(
        "SELECT owner, content FROM scrolls WHERE id = ?", (scroll_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return render_template("council/scroll.html",
                               found=False, scroll_id=scroll_id)
    return render_template("council/scroll.html", found=True,
                           scroll_id=scroll_id, owner=row[0], content=row[1])


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


init_council_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
