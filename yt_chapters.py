#!/usr/bin/env python3
"""
yt-chapters: päättyneiden YouTube-livelähetysten kuvaukset ja aikaleimat
git-repon kautta.

Kulku:
  1. Livelähetys päättyy -> odotetaan, että YouTube saa tekstityksen valmiiksi.
  2. Botti vie repoon videos/<pvm>-<ID>/: description.txt (nykyinen kuvaus),
     transcript.txt, subtitles.srt, meta.json ja valinnaisesti ehdotus.txt
     (Claude API:n aikaleimaehdotus).
  3. Muokkaat description.txt:tä ja pushaat.
  4. Botti huomaa muutoksen, tarkistaa aikaleimat ja päivittää kuvauksen
     YouTubeen. Ongelmista se kirjoittaa samaan kansioon VIRHEET.txt:n.

Komennot:
  auth [--port N]   OAuth-kirjautuminen (kerran, ks. README)
  run               yksi kierros (systemd-timer ajaa tätä)
  add VIDEO_ID      lisää video (myös tavallinen video) tai hae tekstitys uudelleen
  status            seurattujen videoiden tila
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import logging
import os
import re
import smtplib
import sqlite3
import subprocess
import tomllib
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]  # sama kuin auth.py:ssä
MAX_DESCRIPTION = 5000
MIN_CHAPTER_GAP = 10
MAX_ATTEMPTS = 3

WAITING, IN_REPO, FAILED = "waiting", "in_repo", "failed"
ERRORS_FILE = "VIRHEET.txt"
CONFLICT_FILE = "description.youtube.txt"

log = logging.getLogger("yt-chapters")

CHAPTER_RULES = """\
- Ensimmäinen aikaleima on 00:00, ja aikaleimoja on vähintään kolme.
- Aikaleimat ovat nousevassa järjestyksessä, ja niiden väli on vähintään 10 sekuntia.
- Aikaleimarivit ovat kuvauksessa yhtenäisenä lohkona, muoto `MM:SS Otsikko` tai `H:MM:SS Otsikko`.
- Tavoittele merkityksellisiä aiheenvaihdoksia, tyypillisesti 3–10 minuutin välein.
- Otsikot ovat lyhyitä (enintään 60 merkkiä) ja sisältöä kuvaavia, eikä niissä ole merkkejä < tai >.
- Aikaleima osoittaa kohtaan, jossa aihe tekstityksen perusteella oikeasti alkaa.
- Olemassa olevista aikaleimoista säilytetään osuvat, väärät ajat korjataan ja puuttuvat lisätään.
- Sisältöä, jota tekstityksessä ei ole, ei keksitä."""

SYSTEM_PROMPT = f"""Teet YouTube-videoiden lukumerkintöjä (chapters) videon tekstityksen perusteella.
Palauta VAIN yksi JSON-objekti, ei mitään muuta tekstiä:
{{"chapters": [{{"time": "MM:SS tai H:MM:SS", "title": "otsikko"}}], "changes": "lyhyt kuvaus muutoksista"}}

Säännöt:
{CHAPTER_RULES}
- Kerro changes-kentässä suomeksi lyhyesti, mitä muutit olemassa oleviin aikaleimoihin."""

REPO_README = """\
# YouTube-kuvaukset

Tätä repoa ylläpitää yt-chapters-palvelu. Jokaisella videolla on oma kansio `videos/<pvm>-<videoID>/`:

| Tiedosto | Kuka kirjoittaa | Sisältö |
|---|---|---|
| `description.txt` | **sinä** | Videon kuvaus. Pushattu muutos julkaistaan YouTubeen. |
| `transcript.txt` | botti | Tekstitys tiivistettynä muotoon `[aikaleima] teksti` |
| `subtitles.srt` | botti | Alkuperäinen tekstitys |
| `meta.json` | botti | Otsikko, kesto, linkki, tekstitysraita |
| `ehdotus.txt` | botti | Claude API:n kuvausehdotus (jos käytössä). Kopioi siitä description.txt:hen, mitä haluat. |
| `VIRHEET.txt` | botti | Syyt, miksi julkaisu ei onnistunut. Katoaa, kun korjattu versio on julkaistu. |
| `description.youtube.txt` | botti | Ristiriita: kuvausta on muokattu YouTubessa. Yhdistä muutokset description.txt:hen ja poista tämä tiedosto. |

Palvelu tarkistaa repon tunnin välein.

## Aikaleimojen säännöt

{rules}
"""

REPO_CLAUDE_MD = """\
# Ohjeet Claude Codelle

Repossa ovat YouTube-videoiden kuvaukset. Rakenne on kuvattu README.md:ssä.

Kun sinua pyydetään tekemään tai korjaamaan videon aikaleimat:
1. Lue videon kansiosta `transcript.txt` (muoto `[aikaleima] teksti`) ja `meta.json` (kesto).
2. Muokkaa **vain** tiedostoa `description.txt`. Korvaa olemassa oleva aikaleimalohko tai lisää uusi otsikon "Sisältö:" alle. Muu kuvausteksti säilytetään sellaisenaan.
3. Älä muokkaa botin tiedostoja (`transcript.txt`, `subtitles.srt`, `meta.json`, `ehdotus.txt`, `VIRHEET.txt`, `description.youtube.txt`).
4. Committaa, mutta älä pushaa ellei sitä pyydetä. Push julkaisee kuvauksen YouTubeen.

Aikaleimojen säännöt:
{rules}
"""


# ---------------------------------------------------------------- apurit

def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(d: dt.datetime) -> str:
    return d.isoformat(timespec="seconds")


def parse_iso(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def norm(s: str) -> str:
    """Rivinvaihdot ja reunojen tyhjät normalisoituna, jotta vertailu on vakaa."""
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").split("\n")).strip()


def sha(s: str) -> str:
    return hashlib.sha256(norm(s).encode()).hexdigest()


def fmt_ts(sec: int, hours: bool = False) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if hours or h else f"{m:02d}:{s:02d}"


TS_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,3}):(\d{2})$")


def parse_ts(s: str) -> int | None:
    m = TS_RE.match(s.strip())
    if not m:
        return None
    h, mi, se = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
    if se >= 60 or (m.group(1) and mi >= 60):
        return None
    return h * 3600 + mi * 60 + se


DURATION_RE = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?")


def parse_duration(s: str) -> int:
    m = DURATION_RE.fullmatch(s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def write_text(path: Path, text: str) -> None:
    path.write_text(norm(text) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- tekstitykset

SRT_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.]\d{3}\s*-->")
TAG_RE = re.compile(r"<[^>]+>")


def parse_srt(text: str) -> list[tuple[int, str]]:
    cues = []
    for block in re.split(r"\r?\n[ \t]*\r?\n", text.strip()):
        lines = block.splitlines()
        for i, line in enumerate(lines):
            m = SRT_TIME.search(line)
            if m:
                h, mi, s = map(int, m.groups())
                body = TAG_RE.sub("", " ".join(l.strip() for l in lines[i + 1:])).strip()
                if body:
                    cues.append((h * 3600 + mi * 60 + s, body))
                break
    return cues


def compact_transcript(cues: list[tuple[int, str]], window: int, hours: bool) -> str:
    out, start, buf, last = [], None, [], None
    for t, text in cues:
        if text == last:
            continue
        last = text
        if start is None:
            start = t
        elif t - start >= window:
            out.append(f"[{fmt_ts(start, hours)}] {' '.join(buf)}")
            start, buf = t, []
        buf.append(text)
    if buf:
        out.append(f"[{fmt_ts(start, hours)}] {' '.join(buf)}")
    return "\n".join(out)


def pick_track(items: list[dict], langs: list[str]) -> dict | None:
    kind_rank = {"standard": 0, "asr": 1, "forced": 2}
    serving = [c for c in items if c["snippet"].get("status") == "serving"]

    def rank(c):
        s = c["snippet"]
        lang = s.get("language", "").split("-")[0]
        return (langs.index(lang) if lang in langs else len(langs),
                kind_rank.get(s.get("trackKind", "").lower(), 3))

    return min(serving, key=rank) if serving else None


# ---------------------------------------------------------------- aikaleimat

CHAPTER_LINE = re.compile(
    r"^\s*[(\[]?((?:\d{1,2}:)?\d{1,3}:\d{2})[)\]]?(?:\s+|\s*[-–—:|]\s*)(\S.*)$")


def find_chapter_block(lines: list[str]) -> tuple[int, int] | None:
    best, i = None, 0
    while i < len(lines):
        if CHAPTER_LINE.match(lines[i]):
            j = i
            while j < len(lines) and CHAPTER_LINE.match(lines[j]):
                j += 1
            if j - i >= 2 and (best is None or j - i > best[1] - best[0]):
                best = (i, j)
            i = j
        else:
            i += 1
    return best


def validate_description(text: str, duration: int) -> list[str]:
    """Julkaisua estävät ongelmat käyttäjän kirjoittamassa kuvauksessa."""
    errs = []
    if len(text) > MAX_DESCRIPTION:
        errs.append(f"Kuvaus on {len(text)} merkkiä, YouTuben raja on {MAX_DESCRIPTION}.")
    for n, line in enumerate(text.splitlines(), 1):
        if "<" in line or ">" in line:
            errs.append(f"Rivi {n}: merkit < ja > eivät ole sallittuja YouTuben kuvauksessa.")
    lines = text.splitlines()
    span = find_chapter_block(lines)
    if not span:
        return errs
    times = []
    for n in range(*span):
        ts = CHAPTER_LINE.match(lines[n]).group(1)
        sec = parse_ts(ts)
        if sec is None:
            errs.append(f"Rivi {n + 1}: virheellinen aikaleima {ts}.")
        else:
            times.append((n + 1, sec))
    if times:
        if times[0][1] != 0:
            errs.append(f"Rivi {times[0][0]}: ensimmäisen aikaleiman pitää olla 00:00.")
        if len(times) < 3:
            errs.append(f"Aikaleimoja on {len(times)}, YouTube vaatii vähintään 3.")
        for (_, a), (line_no, b) in zip(times, times[1:]):
            if b <= a:
                errs.append(f"Rivi {line_no}: aikaleima ei ole edellistä suurempi.")
            elif b - a < MIN_CHAPTER_GAP:
                errs.append(f"Rivi {line_no}: alle {MIN_CHAPTER_GAP} s edellisestä aikaleimasta.")
        if duration and times[-1][1] > duration - MIN_CHAPTER_GAP:
            errs.append(f"Rivi {times[-1][0]}: aikaleima on liian lähellä videon loppua "
                        f"(kesto {fmt_ts(duration)}).")
    return errs


def format_chapters(chapters: list[tuple[int, str]], duration: int) -> list[str]:
    hours = duration >= 3600 or any(s >= 3600 for s, _ in chapters)
    return [f"{'00:00' if s == 0 else fmt_ts(s, hours)} {t}" for s, t in chapters]


def normalize_chapters(items: list[dict], duration: int) -> list[tuple[int, str]]:
    chs = []
    for c in items:
        sec = parse_ts(str(c.get("time", "")))
        title = re.sub(r"[<>]", "", str(c.get("title", ""))).strip()[:100]
        if sec is not None and title:
            chs.append((sec, title))
    chs.sort(key=lambda c: c[0])
    if not chs:
        raise ValueError("ei yhtään kelvollista aikaleimaa")
    chs[0] = (0, chs[0][1])
    out = [chs[0]]
    for sec, title in chs[1:]:
        if sec - out[-1][0] < MIN_CHAPTER_GAP:
            continue
        if duration and sec > duration - MIN_CHAPTER_GAP:
            continue
        out.append((sec, title))
    if len(out) < 3:
        raise ValueError(f"vain {len(out)} kelvollista aikaleimaa, YouTube vaatii vähintään 3")
    return out


def build_description(old: str, chapters: list[tuple[int, str]], duration: int, header: str) -> str:
    lines = old.splitlines()
    block = format_chapters(chapters, duration)
    span = find_chapter_block(lines)
    if span:
        new = lines[:span[0]] + block + lines[span[1]:]
    else:
        new = list(lines)
        if new and new[-1].strip():
            new.append("")
        if header:
            new.append(header)
        new += block
    return "\n".join(new).strip()


# ---------------------------------------------------------------- kielimalli (valinnainen)

def llm_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("vastauksessa ei ole JSON-objektia")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("chapters"), list):
        raise ValueError("JSONista puuttuu chapters-lista")
    return data


def llm_proposal(cfg, title: str, description: str, transcript: str, duration: int) -> str:
    """Palauttaa ehdotetun koko kuvauksen. Vaatii [llm] enabled = true."""
    import anthropic  # ladataan vain tarvittaessa

    g, lc = cfg["general"], cfg["llm"]
    client = anthropic.Anthropic(api_key=lc.get("api_key") or None)
    lines = description.splitlines()
    span = find_chapter_block(lines)
    existing = "\n".join(lines[span[0]:span[1]]) if span else "(ei aikaleimoja)"
    prompt = (f"Konteksti: {g.get('context', '')}\nVideon otsikko: {title}\n"
              f"Videon kesto: {fmt_ts(duration) if duration else 'tuntematon'}\n\n"
              f"Nykyinen kuvaus:\n\"\"\"\n{description}\n\"\"\"\n\n"
              f"Nykyiset aikaleimat:\n{existing}\n\n"
              f"Tekstitys muodossa [aikaleima] teksti:\n{transcript}")
    messages = [{"role": "user", "content": prompt}]
    last_err = None
    for _ in range(2):
        resp = client.messages.create(model=lc.get("model", "claude-sonnet-5"),
                                      max_tokens=int(lc.get("max_tokens", 4096)),
                                      system=SYSTEM_PROMPT, messages=messages)
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            data = llm_json(text)
            chapters = normalize_chapters(data["chapters"], duration)
            new = build_description(description, chapters, duration,
                                    g.get("chapters_header", "Sisältö:"))
            changes = str(data.get("changes", "")).strip()
            return new + (f"\n\n# Muutokset (poista tämä rivi): {changes}" if changes else "")
        except (ValueError, TypeError, AttributeError) as ex:
            last_err = ex
            messages += [{"role": "assistant", "content": text or "(tyhjä)"},
                         {"role": "user", "content": f"Vastaus ei kelpaa: {ex}. Palauta korjattu JSON."}]
    raise RuntimeError(f"kielimalli ei tuottanut kelvollisia aikaleimoja: {last_err}")


# ---------------------------------------------------------------- YouTube

def state_dir(cfg) -> Path:
    p = Path(cfg["general"].get("state_dir", "/var/lib/yt-chapters"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def youtube_client(cfg):
    tp = state_dir(cfg) / "token.json"
    if not tp.exists():
        raise SystemExit(f"{tp} puuttuu, aja ensin: yt_chapters.py auth")
    creds = Credentials.from_authorized_user_file(str(tp), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        tp.write_text(creds.to_json())
        os.chmod(tp, 0o600)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_video(yt, vid: str) -> dict:
    items = yt.videos().list(part="snippet,contentDetails", id=vid).execute().get("items", [])
    if not items:
        raise RuntimeError(f"videota {vid} ei löydy")
    return items[0]


def update_description(yt, vid: str, description: str) -> str:
    """Päivittää vain kuvauksen. Palauttaa YouTuben tallentaman kuvauksen."""
    sn = get_video(yt, vid)["snippet"]
    # videos.update korvaa koko snippetin: mukaan kaikki kentät, jotka halutaan säilyttää
    snippet = {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage",
                                  "defaultAudioLanguage") if k in sn}
    snippet["description"] = description
    resp = yt.videos().update(part="snippet", body={"id": vid, "snippet": snippet}).execute()
    return resp.get("snippet", {}).get("description", description)


# ---------------------------------------------------------------- git

def web_url(repo_url: str) -> str | None:
    """git@github.com:owner/repo.git tai https://github.com/owner/repo.git -> selainosoite."""
    m = re.match(r"^(?:\w+://)?(?:[^@/]+@)?([^:/]+)[:/](.+?)(?:\.git)?/?$", repo_url)
    return f"https://{m[1]}/{m[2]}" if m else None


class Repo:
    def __init__(self, cfg):
        gc = cfg["git"]
        sd = state_dir(cfg)
        self.path = sd / "repo"
        self.url = gc["repo_url"]
        self.branch = gc.get("branch", "main")
        self.web_url = gc.get("web_url") or web_url(self.url)
        key = gc.get("ssh_key", str(sd / "ssh" / "id_ed25519"))
        name = gc.get("author_name", "yt-chapters")
        mail = gc.get("author_email", "yt-chapters@localhost")
        self.env = {
            **os.environ,
            "HOME": str(sd),
            "GIT_SSH_COMMAND": (f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
                                f"-o StrictHostKeyChecking=accept-new "
                                f"-o UserKnownHostsFile={sd / 'ssh' / 'known_hosts'}"),
            "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": mail,
            "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": mail,
            "GIT_TERMINAL_PROMPT": "0",
        }

    def git(self, *args, check=True, cwd=None) -> subprocess.CompletedProcess:
        r = subprocess.run(["git", *args], cwd=cwd or self.path, env=self.env,
                           capture_output=True, text=True, timeout=120)
        if check and r.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r

    def folder_url(self, rel: str) -> str | None:
        return f"{self.web_url}/tree/{self.branch}/{rel}" if self.web_url else None

    def remote_has_branch(self) -> bool:
        return bool(self.git("ls-remote", "--heads", "origin", self.branch).stdout.strip())

    def in_history(self, rel: str) -> bool:
        # Tyhjässä repossa git log epäonnistuu, jolloin tiedostoa ei ole ollut
        return bool(self.git("log", "-1", "--format=%H", "--", rel, check=False).stdout.strip())

    def ensure(self) -> None:
        if not (self.path / ".git").exists():
            self.git("clone", self.url, str(self.path), cwd=self.path.parent)
        if self.remote_has_branch():
            self.git("checkout", self.branch)
        else:
            self.git("checkout", "-B", self.branch)
        created = []
        for name, template in (("README.md", REPO_README), ("CLAUDE.md", REPO_CLAUDE_MD)):
            # Luodaan vain kerran: käyttäjän poistamaa tiedostoa ei palauteta
            if not (self.path / name).exists() and not self.in_history(name):
                write_text(self.path / name, template.format(rules=CHAPTER_RULES))
                created.append(name)
        if created:
            self.commit_push("Alusta repo", created)

    def pull(self) -> None:
        if self.remote_has_branch():
            self.git("pull", "--rebase", "--autostash", "origin", self.branch)

    def commit_push(self, message: str, paths: list[str]) -> None:
        self.git("add", "-A", "--", *paths)
        if self.git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return  # ei muutoksia
        self.git("commit", "-m", message)
        if self.git("push", "origin", self.branch, check=False).returncode:
            self.pull()  # joku pushasi välissä
            self.git("push", "origin", self.branch)


# ---------------------------------------------------------------- tila

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY,
  title TEXT,
  status TEXT NOT NULL,
  ended_at TEXT,
  added_at TEXT NOT NULL,
  updated_at TEXT,
  last_checked TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  dir TEXT,
  duration INTEGER,
  repo_hash TEXT,      -- description.txt, jonka botti viimeksi kirjoitti tai julkaisi
  yt_hash TEXT,        -- YouTuben kuvaus, kun botti viimeksi näki sen
  published_at TEXT,
  last_error TEXT
)"""


def open_db(cfg) -> sqlite3.Connection:
    db = sqlite3.connect(state_dir(cfg) / "state.db")
    db.row_factory = sqlite3.Row
    db.execute(SCHEMA)
    return db


def update(db, vid: str, **fields) -> None:
    fields["updated_at"] = iso(now())
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE videos SET {cols} WHERE video_id=?", (*fields.values(), vid))
    db.commit()


# ---------------------------------------------------------------- ilmoitukset (valinnainen)

def notify(cfg, subject: str, body: str) -> None:
    e = cfg.get("email")
    if not e or not e.get("enabled", True):
        return
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = e["from_address"], e["to_address"], subject
        msg["Message-ID"] = make_msgid(domain=e["from_address"].rsplit("@", 1)[-1])
        msg.set_content(body)
        port = int(e.get("smtp_port", 465))
        if e.get("smtp_starttls", False):
            with smtplib.SMTP(e["smtp_host"], port, timeout=30) as s:
                s.starttls()
                s.login(e["username"], e["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(e["smtp_host"], port, timeout=30) as s:
                s.login(e["username"], e["password"])
                s.send_message(msg)
    except Exception:
        log.exception("ilmoituksen lähetys epäonnistui")


# ---------------------------------------------------------------- kierroksen vaiheet

def discover(yt, db, cfg) -> None:
    start_after = parse_iso(cfg["general"]["start_after"])
    page = None
    while True:
        resp = yt.liveBroadcasts().list(part="snippet", broadcastStatus="completed",
                                        broadcastType="all", maxResults=50,
                                        pageToken=page).execute()
        for b in resp.get("items", []):
            end = b["snippet"].get("actualEndTime")
            if not end or parse_iso(end) < start_after:
                continue
            cur = db.execute(
                "INSERT OR IGNORE INTO videos(video_id,title,status,ended_at,added_at) VALUES (?,?,?,?,?)",
                (b["id"], b["snippet"].get("title"), WAITING, end, iso(now())))
            if cur.rowcount:
                log.info("uusi päättynyt lähetys: %s %s", b["id"], b["snippet"].get("title"))
        db.commit()
        page = resp.get("nextPageToken")
        if not page:
            break


def export_video(yt, repo: Repo, db, cfg, row, track: dict) -> None:
    """Vie tekstitys ja nykyinen kuvaus repoon."""
    g = cfg["general"]
    vid = row["video_id"]
    srt = yt.captions().download_media(id=track["id"], tfmt="srt").execute()
    if isinstance(srt, bytes):
        srt = srt.decode("utf-8", "replace")
    cues = parse_srt(srt)
    if not cues:
        raise RuntimeError("tekstitys on tyhjä")
    video = get_video(yt, vid)
    sn = video["snippet"]
    desc = sn.get("description", "")
    duration = parse_duration(video.get("contentDetails", {}).get("duration", ""))
    hours = duration >= 3600 or cues[-1][0] >= 3600
    transcript = compact_transcript(cues, int(g.get("transcript_window_sec", 15)), hours)

    rel = row["dir"] or f"videos/{(row['ended_at'] or row['added_at'])[:10]}-{vid}"
    d = repo.path / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "subtitles.srt").write_text(srt, encoding="utf-8")
    write_text(d / "transcript.txt", transcript)
    (d / "meta.json").write_text(json.dumps({
        "video_id": vid, "title": sn["title"], "url": f"https://youtu.be/{vid}",
        "studio": f"https://studio.youtube.com/video/{vid}/edit",
        "duration": fmt_ts(duration) if duration else None, "duration_sec": duration,
        "caption_language": track["snippet"].get("language"),
        "caption_kind": track["snippet"].get("trackKind"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Älä kirjoita käyttäjän julkaisemattomien muutosten päälle (esim. add olemassa olevalle)
    desc_file = d / "description.txt"
    user_edits = (desc_file.exists() and row["repo_hash"]
                  and sha(desc_file.read_text(encoding="utf-8")) != row["repo_hash"])
    if not user_edits:
        write_text(desc_file, desc)

    if cfg.get("llm", {}).get("enabled", False):
        try:
            write_text(d / "ehdotus.txt", llm_proposal(cfg, sn["title"], desc, transcript, duration))
        except Exception as ex:
            log.exception("%s: kielimallin ehdotus epäonnistui", vid)
            write_text(d / "ehdotus.txt", f"Ehdotusta ei saatu tehtyä: {ex}")

    repo.commit_push(f"Tekstitys ja kuvaus: {sn['title']} ({vid})", [rel])
    update(db, vid, status=IN_REPO, title=sn["title"], dir=rel, duration=duration,
           repo_hash=row["repo_hash"] if user_edits else sha(desc), yt_hash=sha(desc),
           last_error=None, attempts=0)
    folder = repo.folder_url(rel)
    notify(cfg, f"Uusi video repossa: {sn['title']}",
           f"Muokkaa {rel}/description.txt ja pushaa, niin kuvaus päivittyy YouTubeen.\n\n"
           f"Video: https://youtu.be/{vid}\n"
           + (f"Kansio: {folder}\n" if folder else ""))
    log.info("%s: viety repoon (%s)", vid, rel)


def process_waiting(yt, repo: Repo, db, cfg) -> None:
    g = cfg["general"]
    interval = dt.timedelta(minutes=int(g.get("caption_check_interval_min", 60)))
    max_wait = dt.timedelta(hours=int(g.get("caption_max_wait_hours", 72)))
    langs = g.get("caption_languages", ["fi"])
    for row in db.execute("SELECT * FROM videos WHERE status=?", (WAITING,)).fetchall():
        vid = row["video_id"]
        if row["last_checked"] and now() - parse_iso(row["last_checked"]) < interval:
            continue
        update(db, vid, last_checked=iso(now()))
        try:
            items = yt.captions().list(part="snippet", videoId=vid).execute().get("items", [])
            track = pick_track(items, langs)
            if track is None:
                if now() - parse_iso(row["ended_at"] or row["added_at"]) > max_wait:
                    update(db, vid, status=FAILED, last_error="tekstitystä ei löytynyt")
                    notify(cfg, f"Ei tekstitystä: {row['title']}",
                           f"https://youtu.be/{vid}\nUusi yritys: yt_chapters.py add {vid}")
                else:
                    log.info("%s: tekstitys ei vielä valmis", vid)
                continue
            export_video(yt, repo, db, cfg, row, track)
        except Exception as ex:
            log.exception("%s: vienti epäonnistui", vid)
            attempts = row["attempts"] + 1
            update(db, vid, attempts=attempts, last_error=str(ex),
                   **({"status": FAILED} if attempts >= MAX_ATTEMPTS else {}))
            if attempts >= MAX_ATTEMPTS:
                notify(cfg, f"Vienti repoon epäonnistui: {row['title']}",
                       f"https://youtu.be/{vid}\nVirhe: {ex}\nUusi yritys: yt_chapters.py add {vid}")


def process_repo_changes(yt, repo: Repo, db, cfg) -> None:
    """Julkaise description.txt-muutokset, jotka on pushattu repoon."""
    for row in db.execute("SELECT * FROM videos WHERE status=? AND dir IS NOT NULL",
                          (IN_REPO,)).fetchall():
        vid, rel = row["video_id"], row["dir"]
        d = repo.path / rel
        desc_file = d / "description.txt"
        if not desc_file.exists():
            continue
        text = norm(desc_file.read_text(encoding="utf-8"))
        if sha(text) == row["repo_hash"]:
            continue  # ei muutoksia
        if (d / CONFLICT_FILE).exists():
            log.info("%s: odottaa ristiriidan ratkaisua", vid)
            continue

        errs = validate_description(text, row["duration"] or 0)
        if errs:
            body = ("Kuvausta ei julkaistu, koska siinä on seuraavat ongelmat:\n\n"
                    + "\n".join(f"- {e}" for e in errs)
                    + "\n\nKorjaa description.txt ja pushaa uudelleen.")
            if not (d / ERRORS_FILE).exists() or norm((d / ERRORS_FILE).read_text()) != norm(body):
                write_text(d / ERRORS_FILE, body)
                repo.commit_push(f"Virheitä kuvauksessa: {row['title']} ({vid})", [rel])
                notify(cfg, f"Kuvauksessa virheitä: {row['title']}", body)
            log.info("%s: validointi epäonnistui", vid)
            continue

        yt_desc = get_video(yt, vid)["snippet"].get("description", "")
        if sha(yt_desc) != row["yt_hash"]:
            write_text(d / CONFLICT_FILE, yt_desc)
            repo.commit_push(f"Ristiriita: kuvausta muokattu YouTubessa ({vid})", [rel])
            update(db, vid, yt_hash=sha(yt_desc))
            notify(cfg, f"Ristiriita: {row['title']}",
                   f"Kuvausta on muokattu YouTubessa. Yhdistä muutokset tiedostosta "
                   f"{rel}/{CONFLICT_FILE} description.txt:hen, poista {CONFLICT_FILE} ja pushaa.")
            continue

        try:
            saved = update_description(yt, vid, text)
        except Exception as ex:
            log.exception("%s: julkaisu epäonnistui", vid)
            update(db, vid, last_error=str(ex))
            continue
        update(db, vid, repo_hash=sha(text), yt_hash=sha(saved),
               published_at=iso(now()), last_error=None)
        if (d / ERRORS_FILE).exists():
            (d / ERRORS_FILE).unlink()
            repo.commit_push(f"Julkaistu: {row['title']} ({vid})", [rel])
        folder = repo.folder_url(rel)
        notify(cfg, f"Kuvaus päivitetty: {row['title']}",
               f"Botti päivitti videon kuvauksen YouTubeen.\n\n"
               f"Video: https://youtu.be/{vid}\n"
               + (f"Kansio: {folder}\n" if folder else ""))
        log.info("%s: julkaistu", vid)


# ---------------------------------------------------------------- komennot

def cmd_auth(cfg, args) -> None:
    secret = cfg.get("youtube", {}).get("client_secret")
    if not secret:
        raise SystemExit("config.toml:stä puuttuu [youtube]-osio ja sen client_secret-rivi, ks. README-VPS.md")
    if not Path(secret).exists():
        raise SystemExit(f"{secret} puuttuu (config.toml, [youtube] client_secret)")
    flow = InstalledAppFlow.from_client_secrets_file(secret, SCOPES)
    creds = flow.run_local_server(host="localhost", port=args.port, open_browser=False,
                                  access_type="offline", prompt="consent")
    tp = state_dir(cfg) / "token.json"
    tp.write_text(creds.to_json())
    os.chmod(tp, 0o600)
    (state_dir(cfg) / "auth_alert_sent").unlink(missing_ok=True)
    print(f"Token tallennettu: {tp}")


def cmd_run(cfg, args) -> None:
    sd = state_dir(cfg)
    lock = open(sd / "run.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.info("edellinen ajo on vielä käynnissä")
        return
    db = open_db(cfg)
    try:
        yt = youtube_client(cfg)
    except RefreshError as ex:
        marker = sd / "auth_alert_sent"
        if not marker.exists():
            notify(cfg, "yt-chapters: YouTube-kirjautuminen vanhentunut",
                   f"Refresh token ei kelpaa ({ex}).\nKirjaudu uudelleen omalla koneella (auth.py) "
                   f"ja korvaa secret YOUTUBE_TOKEN. Ohje: README.md, Vianetsintä.")
            marker.touch()
        raise SystemExit(1)
    repo = Repo(cfg)
    repo.ensure()
    repo.pull()
    run_cycle(yt, repo, db, cfg)


def run_cycle(yt, repo: Repo, db, cfg) -> None:
    process_repo_changes(yt, repo, db, cfg)
    discover(yt, db, cfg)
    process_waiting(yt, repo, db, cfg)
    # 'add' repossa jo olevalle videolle palauttaa sen jonoon, jolloin ensimmäinen
    # julkaisukierros ohittaa sen. Viennin jälkeen julkaistaan siksi vielä kerran,
    # jotta pushatut muokkaukset päätyvät YouTubeen samassa ajossa.
    process_repo_changes(yt, repo, db, cfg)


def cmd_add(cfg, args) -> None:
    db = open_db(cfg)
    t = iso(now())
    db.execute(
        "INSERT INTO videos(video_id,status,added_at,updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(video_id) DO UPDATE SET status=excluded.status, attempts=0, "
        "last_checked=NULL, last_error=NULL, updated_at=excluded.updated_at",
        (args.video_id, WAITING, t, t))
    db.commit()
    print(f"{args.video_id} jonossa, käsitellään seuraavalla ajolla")


def cmd_status(cfg, args) -> None:
    db = open_db(cfg)
    for r in db.execute("SELECT * FROM videos ORDER BY added_at DESC"):
        pub = f"  julkaistu {r['published_at']}" if r["published_at"] else ""
        err = f"  virhe: {r['last_error']}" if r["last_error"] else ""
        print(f"{r['video_id']}  {r['status']:<8} {r['dir'] or '-'}  {r['title'] or ''}{pub}{err}")


def main() -> None:
    ap = argparse.ArgumentParser(description="YouTube-kuvaukset git-repon kautta")
    ap.add_argument("--config", default="/etc/yt-chapters/config.toml")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth").add_argument("--port", type=int, default=8765)
    sub.add_parser("run")
    sub.add_parser("add").add_argument("video_id")
    sub.add_parser("status")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    {"auth": cmd_auth, "run": cmd_run, "add": cmd_add, "status": cmd_status}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
