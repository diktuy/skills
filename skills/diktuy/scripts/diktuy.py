#!/usr/bin/env python3
"""Диктуй — CLI к API api.diktuy.ru/v1 для ИИ-агентов и людей.

Встречи из приложения Диктуй, поиск по ним, задачи, расшифровка файлов и записей
по ссылке, имена говорящих, уведомления (вебхуки), тариф и кредиты.

Только стандартная библиотека Python 3.8+, работает на Windows, macOS и Linux.
Ключ: `diktuy.py login` (сохранится в ~/.diktuy-skill/api-key) или переменная DIKTUY_API_KEY.
Справка: diktuy.py -h, diktuy.py <команда> -h
Скилл целиком: https://github.com/diktuy/skills
"""
import argparse
import json
import mimetypes
import os
import re
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSION = "1.1.0"
BASE = os.environ.get("DIKTUY_BASE_URL", "https://api.diktuy.ru").rstrip("/")
# ~/.diktuy занята приложением Диктуй (его база и вход) — у скилла своя папка
HOME = Path(os.environ.get("DIKTUY_SKILL_HOME") or Path.home() / ".diktuy-skill")
KEYFILE = HOME / "api-key"
OUT_DIR = Path(os.environ.get("DIKTUY_OUT") or Path(tempfile.gettempdir()) / "diktuy")
UA = f"diktuy-skill/{VERSION} (+https://github.com/diktuy/skills)"
MEETING_ID = re.compile(r"^[0-9a-f]{32}$")
FILE_LIMIT = 25 * 1024 * 1024
# Длиннее — не в вывод, а в файл: час встречи ≈ 60 тыс. знаков ≈ 15–30 тыс. токенов в контексте агента
INLINE_LIMIT = int(os.environ.get("DIKTUY_INLINE_LIMIT") or 12000)

PLAN_NAMES = {"free": "Бесплатный", "pro": "Профи", "max": "Макс", "unlimited": "Макс", "business": "Бизнес"}
HINTS = {
    "auth_required": "Нет ключа. Создайте его на https://diktuy.ru/dashboard/api и выполните `diktuy.py login`.",
    "invalid_key": "Новый ключ — на https://diktuy.ru/dashboard/api, затем `diktuy.py login`.",
    "plan_required": "API работает на тарифах Профи и Макс (и на месте от компании). Тарифы: https://diktuy.ru/pricing",
    "insufficient_scope": "У ключа нет нужного права. Создайте новый ключ на https://diktuy.ru/dashboard/api",
    "insufficient_credits": "Не хватает кредитов. Остаток — `diktuy.py me`; пакеты кредитов — https://diktuy.ru/pricing",
    "too_long": "Файлом — до 30 минут. Длиннее — загрузите на Яндекс Диск или Google Диск и `diktuy.py submit <ссылка>`.",
    "payload_too_large": "Файлом — до 25 МБ. Больше — загрузите на Яндекс Диск или Google Диск и `diktuy.py submit <ссылка>`.",
    "rate_limited": "Лимит — 60 запросов в минуту на ключ. Подождите минуту или сузьте период (--since).",
    "transcription_failed": "Сбой распознавания, кредиты вернулись. Повторите запрос.",
    "bad_media": "Из файла не удалось прочитать звук. Проверьте, что файл открывается и в нём есть дорожка со звуком.",
}


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def die(msg, code=1):
    eprint(f"ОШИБКА: {msg}")
    sys.exit(code)


# ---------- ключ и сеть ----------

def api_key():
    k = os.environ.get("DIKTUY_API_KEY", "").strip()
    if k:
        return k
    if KEYFILE.exists():
        k = KEYFILE.read_text(encoding="utf-8").strip()
        if k:
            return k
    die("Ключа API нет.\n"
        "  1. Создайте ключ: https://diktuy.ru/dashboard/api → «Создать ключ» (тарифы Профи и Макс).\n"
        "  2. Сохраните его: `diktuy.py login` (ввод скрыт) или переменная окружения DIKTUY_API_KEY.")


class ApiError(Exception):
    def __init__(self, status, body, request_id):
        self.status = status
        try:
            self.problem = json.loads(body)
        except ValueError:
            self.problem = {"detail": body.decode("utf-8", "replace")[:300]}
        self.code = self.problem.get("code", "")
        self.request_id = request_id or self.problem.get("request_id")
        super().__init__(self.describe())

    def describe(self):
        p = self.problem
        s = f"{self.status} {self.code}: {p.get('detail') or p.get('title') or ''}"
        for e in p.get("errors") or []:
            s += f"\n  {e.get('path', '')} {e.get('message', '')}"
        if self.code in HINTS:
            s += f"\n  → {HINTS[self.code]}"
        if self.request_id:
            s += f"\n  request_id: {self.request_id} (для поддержки: support@diktuy.ru)"
        return s


# Сначала напрямую: VPN-выход за рубежом сервер может не пустить. Не вышло, а в системе прописан
# прокси (корпоративная сеть) — через него.
_OPENERS = [urllib.request.build_opener(urllib.request.ProxyHandler({}))]
if urllib.request.getproxies():
    _OPENERS.append(urllib.request.build_opener())


def multipart(fields, path):
    boundary = uuid.uuid4().hex
    out = bytearray()
    for name, val in fields.items():
        for v in val if isinstance(val, list) else [val]:
            out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                    f"\r\n\r\n{v}\r\n").encode("utf-8")
    fname = path.name.replace('"', "")
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    out += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"'
            f"\r\nContent-Type: {ctype}\r\n\r\n").encode("utf-8")
    out += path.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def call(method, path, params=None, body=None, upload=None, headers=None, raw=False,
         timeout=60, tries=4, key=None):
    """upload = (fields, Path) — multipart с файлом; raw — вернуть текст как есть."""
    url = BASE + path
    params = {k: v for k, v in (params or {}).items() if v is not None}
    if params:
        url += "?" + urllib.parse.urlencode(params)
    h = {"Authorization": f"Bearer {key or api_key()}", "User-Agent": UA}
    data = None
    if upload:
        data, h["Content-Type"] = multipart(*upload)
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    # Повтор после обрыва безопасен для чтения и для запроса с ключом повтора; файл повторно не шлём —
    # сервер мог его уже расшифровать и списать кредиты
    safe = method == "GET" or "Idempotency-Key" in h
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with _OPENERS[0].open(req, timeout=timeout) as r:
                content = r.read()
        except urllib.error.HTTPError as e:
            content = e.read()
            if e.code in (429, 503) and attempt < tries - 1:
                attempt += 1
                wait = min(int(e.headers.get("Retry-After") or 10), 120)
                eprint(f"… {e.code}, повтор через {wait} с")
                time.sleep(wait)
                continue
            raise ApiError(e.code, content, e.headers.get("X-Request-Id"))
        except urllib.error.URLError as e:  # не достучались до сервера — запрос не ушёл
            if len(_OPENERS) > 1:
                eprint("… напрямую не вышло, пробую через системный прокси")
                _OPENERS.pop(0)
                continue
            if attempt < tries - 1:
                attempt += 1
                time.sleep(3)
                continue
            die(f"нет связи с {BASE}: {e.reason}")
        except (socket.timeout, TimeoutError, ConnectionError) as e:  # оборвалось после отправки
            if safe and attempt < tries - 1:
                attempt += 1
                time.sleep(3)
                continue
            die(f"связь оборвалась: {e}" + ("" if safe else
                ". Проверьте `diktuy.py me`, списались ли кредиты, прежде чем отправлять снова"))
        if raw:
            return content.decode("utf-8")
        return json.loads(content) if content else None


def paged(path, params=None, since=None, limit=None):
    """Листает список (новые сначала). since — остановиться на записи старше даты."""
    cursor, n = None, 0
    while True:
        page = call("GET", path, {**(params or {}), "limit": 100, "cursor": cursor})
        for item in page["data"]:
            ts = item.get("started_at") or item.get("created_at")
            if since and ts and parse_ts(ts) < since:
                return
            yield item
            n += 1
            if limit and n >= limit:
                return
        if not page.get("has_more"):
            return
        cursor = page["next_cursor"]


# ---------- формат ----------

def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def local(s, fmt="%d.%m.%Y %H:%M"):
    return parse_ts(s).astimezone().strftime(fmt) if s else "—"


def dur(sec):
    if sec is None:
        return "—"
    sec = int(round(sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def stamp(sec):
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def parse_since(s):
    if not s or s == "all":
        return None
    m = re.fullmatch(r"(\d+)d", s)
    if m:
        return datetime.now(timezone.utc) - timedelta(days=int(m.group(1)))
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).astimezone()
        except ValueError:
            pass
    die(f"--since: нужно 7d, YYYY-MM-DD, ДД.ММ.ГГГГ или all, а пришло {s!r}")


def tokens(text):
    n = len(text) // 3  # русский текст: 1 токен ≈ 2–3,5 знака, считаем по верхней оценке
    return f"≈ {n // 1000} тыс. токенов" if n >= 1000 else f"≈ {max(n, 1)} токенов"


def write_file(text, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def emit(text, out=None, name=None, full=False):
    """В файл (out), в вывод — или, если текст длинный и out не задан, в файл OUT_DIR/name.md."""
    if not text.endswith("\n"):
        text += "\n"
    if out:
        p = write_file(text, out)
        eprint(f"→ {p} ({len(text)} знаков, {tokens(text)})")
        return
    if name and not full and len(text) > INLINE_LIMIT:
        p = write_file(text, OUT_DIR / f"{name}.md")
        sys.stdout.write(text[:1500].rstrip() + "\n\n…\n")
        print(f"[Текст длинный: {len(text)} знаков, {tokens(text)}. Целиком — в файле {p}. "
              f"Читайте его частями; в вывод целиком — флаг --full.]")
        return
    sys.stdout.write(text)


def as_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------- аккаунт ----------

def cmd_login(a):
    key = (sys.stdin.readline() if a.stdin else "").strip()
    if not key:
        if not sys.stdin.isatty():
            die("запустите `diktuy.py login` в своём терминале — ключ спросит со скрытым вводом; для скриптов — `--stdin`")
        import getpass
        key = getpass.getpass("Ключ API (dk_live_…; ввод не отображается): ").strip()
    if not key.startswith("dk_"):
        die("ключ начинается с dk_live_ — скопируйте его целиком на https://diktuy.ru/dashboard/api")
    d = call("GET", "/v1/me", key=key)
    HOME.mkdir(parents=True, exist_ok=True)
    KEYFILE.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(KEYFILE, 0o600)
    except OSError:
        pass
    eprint(f"Ключ сохранён в {KEYFILE}")
    print_me(d)


def cmd_logout(a):
    gone = [str(f) for f in (KEYFILE,) if f.exists()]
    for f in gone:
        Path(f).unlink()
    emit(f"удалён ключ: {', '.join(gone)}" if gone else "сохранённого ключа нет")
    if os.environ.get("DIKTUY_API_KEY"):
        eprint("Внимание: ключ ещё задан в переменной окружения DIKTUY_API_KEY.")
    eprint("Сам ключ на сервере продолжает действовать — отозвать: https://diktuy.ru/dashboard/api")


def print_me(d):
    p, c, k = d["plan"], d["credits"], d["key"]
    exp = local(p["expires_at"], "%d.%m.%Y") if p.get("expires_at") else "без срока"
    plan = PLAN_NAMES.get(p["type"], p["type"])
    lines = [
        f"Аккаунт  {d['user']['email']}",
        f"Тариф    {plan}, {'действует до ' + exp if p['active'] else 'НЕ действует'}",
        f"Кредиты  {c['available']} доступно: месячные {c['monthly_used']} из {c['monthly_limit']} потрачено"
        f" (период с {local(c['period_start'], '%d.%m.%Y') if c.get('period_start') else '—'}),"
        f" купленные {c['purchased']}. 1 кредит = 1 минута записи",
        f"Ключ     «{k['name']}», права: {', '.join(k['scopes'])}",
    ]
    if not p["active"]:
        lines.append("→ Тариф не действует: кроме `me`, API отвечает 403. Профи или Макс — https://diktuy.ru/pricing")
    elif c["available"] < 30:
        lines.append("→ Кредитов мало: расшифровка списывает 1 кредит за минуту. Пакеты — https://diktuy.ru/pricing")
    emit("\n".join(lines))


def cmd_me(a):
    d = call("GET", "/v1/me")
    emit(as_json(d)) if a.json else print_me(d)


# ---------- встречи ----------

def resolve_meeting(ref):
    """id из 32 hex | last | N (1 = последняя) | кусок названия или даты «28.10»."""
    if MEETING_ID.match(ref):
        return ref
    items = list(paged("/v1/meetings"))
    if not items:
        die("встреч нет: в API попадают встречи, записанные приложением Диктуй на компьютере (Профи и Макс)")
    if ref == "last":
        return items[0]["id"]
    if ref.isdigit():
        n = int(ref)
        if not 1 <= n <= len(items):
            die(f"встреч всего {len(items)}")
        return items[n - 1]["id"]
    q = ref.lower()
    hits = [m for m in items
            if q in m["title"].lower() or q in local(m["started_at"]) or q in (m.get("source") or "").lower()]
    if len(hits) == 1:
        return hits[0]["id"]
    if not hits:
        die(f"нет встречи по «{ref}» — список: `diktuy.py meetings`")
    die(f"под «{ref}» подходит несколько встреч ({len(hits)}), уточните:\n"
        + "\n".join(meeting_line(i, m) for i, m in enumerate(hits, 1)))


def meeting_line(i, m):
    return (f"{i:>3}  {local(m['started_at'])}  {dur(m['duration_seconds']):>8}  {m['speakers_count']} гов.  "
            f"{','.join(m['summaries']) or '—':<20}  {m['id']}  {m['title']}")


def cmd_meetings(a):
    items = list(paged("/v1/meetings", since=parse_since(a.since), limit=a.limit))
    if a.json:
        return emit(as_json(items))
    if not items:
        return emit("встреч нет" + (" за этот период" if a.since else ""))
    emit("  №  начало            длит.    гов.   выжимки               id  название\n"
         + "\n".join(meeting_line(i, m) for i, m in enumerate(items, 1)))


def summaries_md(d, template=None):
    return "\n\n".join(f"## Выжимка «{s['template']}»\n\n{s['markdown'].strip()}"
                       for s in d["summary_texts"] if template in (None, s["template"]))


def questions_md(d):
    return "\n\n".join(f"**Вопрос:** {q['question']}\n\n**Ответ:** {q['answer']}" for q in d["questions"])


def cmd_meeting(a):
    mid = resolve_meeting(a.ref)
    name = f"meeting-{mid[:8]}"
    if a.summary is not None or a.questions:
        d = call("GET", f"/v1/meetings/{mid}")
        head = f"# {d['title']}\n\n{local(d['started_at'])}, {dur(d['duration_seconds'])}, id {mid}"
        body = []
        if a.summary is not None:
            tpl = a.summary or None
            body.append(summaries_md(d, tpl) or
                        f"_Выжимки{' «' + tpl + '»' if tpl else ''} нет; готовые: {', '.join(d['summaries']) or 'никаких'}. "
                        "Выжимку делают в приложении Диктуй — или агент сам по расшифровке._")
        if a.questions:
            body.append("## Вопросы к встрече\n\n" + (questions_md(d) or "_вопросов не задавали_"))
        return emit(head + "\n\n" + "\n\n".join(body), a.out, f"{name}-summary", a.full)
    if a.format == "json":
        return emit(as_json(call("GET", f"/v1/meetings/{mid}")), a.out, f"{name}-json", a.full)
    emit(call("GET", f"/v1/meetings/{mid}", {"format": a.format}, raw=True), a.out, f"{name}-{a.format}", a.full)


def snippet(text, rx, width=120):
    m = rx.search(text)
    lo, hi = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if lo else "") + text[lo:hi].strip() + ("…" if hi < len(text) else "")


def cmd_search(a):
    # без --regex — с начала слова: «тариф» найдёт «тарифы», «Елена» не найдёт «выделена»
    rx = re.compile(a.query if a.regex else r"(?<!\w)" + re.escape(a.query), re.I)
    found = 0
    for m in paged("/v1/meetings", since=parse_since(a.since)):
        d = call("GET", f"/v1/meetings/{m['id']}")
        hits = [f"  [говорящий] {s['name']}" for s in d["speakers"] if rx.search(s["name"])]
        hits += [f"  [{stamp(s['start'])}] {s['speaker_name']}: {snippet(s['text'], rx)}"
                 for s in d["segments"] if rx.search(s["text"])]
        hits += [f"  [выжимка {s['template']}] {snippet(line.strip(), rx)}"
                 for s in d["summary_texts"] for line in s["markdown"].splitlines() if rx.search(line)]
        hits += [f"  [вопрос] {q['question']} → {snippet(q['answer'], rx) if rx.search(q['answer']) else q['answer'][:240]}"
                 for q in d["questions"] if rx.search(q["question"]) or rx.search(q["answer"])]
        if hits:
            found += 1
            print(f"\n# {d['title']} — {local(d['started_at'])}, {dur(d['duration_seconds'])}, id {m['id']}")
            print("\n".join(hits[: a.max]))
            if len(hits) > a.max:
                print(f"  … ещё {len(hits) - a.max}")
    if not found:
        print(f"ничего не нашлось по «{a.query}» за период {a.since} (шире — --since 90d или --since all)")


def cmd_tasks(a):
    blocks, missing = [], []
    for m in paged("/v1/meetings", since=parse_since(a.since)):
        if "tasks" not in m["summaries"]:
            missing.append(m)
            continue
        d = call("GET", f"/v1/meetings/{m['id']}")
        md = next((s["markdown"] for s in d["summary_texts"] if s["template"] == "tasks"), "")
        blocks.append(f"## {d['title']} — {local(d['started_at'])}, id {m['id']}\n\n{md.strip()}")
    text = "\n\n".join(blocks) or f"_За период {a.since} нет встреч с выжимкой «Задачи»._"
    if missing:
        text += ("\n\n## Без выжимки «Задачи»\n\nЗадачи по ним агент может выписать сам из расшифровки "
                 "(`diktuy.py meeting <id> --format text`).\n\n"
                 + "\n".join(f"- {local(m['started_at'])}, {dur(m['duration_seconds'])} — {m['title']} (id {m['id']})"
                             for m in missing))
    emit(text, a.out, "tasks", a.full)


# ---------- расшифровка файлом (сразу) ----------

MEDIA_EXT = {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".webm", ".flac", ".mp4", ".mov", ".amr", ".aac", ".wma", ".mkv"}


def expand_files(args):
    """Папка → её аудио и видео; шаблон *.ogg раскрываем сами: PowerShell и cmd этого не делают."""
    import glob
    out = []
    for f in args:
        p = Path(f)
        if p.is_dir():
            out += sorted(x for x in p.iterdir() if x.suffix.lower() in MEDIA_EXT)
        elif any(c in f for c in "*?["):
            out += sorted(Path(x) for x in glob.glob(f))
        else:
            out.append(p)
    if not out:
        die("не нашлось ни одного файла")
    return out


def cmd_transcribe(a):
    files = expand_files(a.files)
    for p in files:
        if not p.is_file():
            die(f"нет файла {p}")
        if p.stat().st_size > FILE_LIMIT:
            die(f"{p.name}: {p.stat().st_size / 2**20:.1f} МБ, а файлом — до 25 МБ и 30 минут. "
                "Длиннее — загрузите на Яндекс Диск или Google Диск и `diktuy.py submit <ссылка>`")
    if len(files) > 1 and a.out:
        die("несколько файлов — вместо --out укажите --out-dir")
    fmt = "verbose_json" if a.words else a.format
    ext = {"text": "txt", "json": "json", "verbose_json": "json", "srt": "srt", "vtt": "vtt"}[fmt]
    total = 0
    for p in files:
        fields = {"response_format": "json" if fmt == "text" else fmt}
        if a.words:
            fields["timestamp_granularities[]"] = ["word", "segment"]
        if a.language:
            fields["language"] = a.language
        if a.prompt:
            fields["prompt"] = a.prompt
        res = call("POST", "/v1/audio/transcriptions", upload=(fields, p), raw=True, timeout=900)
        if fmt in ("srt", "vtt"):
            text = res
            eprint(f"{p.name}: готово (кредиты — `diktuy.py me`)")
        else:
            d = json.loads(res)
            total += d.get("credits_charged") or 0
            eprint(f"{p.name}: {dur(d.get('duration'))}, списано {d.get('credits_charged')} кр., "
                   f"осталось {d.get('credits_remaining')}")
            text = d["text"] if fmt == "text" else as_json(d)
        out = a.out or (Path(a.out_dir) / f"{p.stem}.{ext}" if a.out_dir else None)
        if len(files) > 1 and not out:
            text = f"=== {p.name} ===\n{text}"
        emit(text, out, f"transcribe-{p.stem}", a.full)
    if len(files) > 1 and total:
        eprint(f"всего списано {total} кр.")


# ---------- расшифровка по ссылке (очередь) ----------

def job_line(j):
    st = j["status"]
    if st == "processing":
        st += f" {j.get('stage') or ''} {j.get('progress', 0)}%"
    return (f"{j['id']}  {local(j['created_at'])}  {st:<28}  {dur(j.get('duration_seconds')):>8}  "
            f"{j.get('credits_charged', 0)} кр.  {j.get('external_id') or ''}  {j.get('title') or j.get('audio_url') or ''}")


def wait_job(jid, timeout):
    t0, last = time.time(), None
    while True:
        j = call("GET", f"/v1/transcriptions/{jid}")
        if j["status"] in ("completed", "failed", "cancelled"):
            return j
        line = job_line(j)
        if line != last:
            eprint("… " + line)
            last = line
        if time.time() - t0 > timeout:
            die(f"не дождался за {timeout} с — задание {jid} идёт дальше, проверьте `diktuy.py job {jid}`", 2)
        time.sleep(min(30, max(5, (j.get("eta_seconds") or 10) / 3)))


def output_job(j, fmt, out, full):
    if j["status"] != "completed":
        err = j.get("error") or {}
        die(f"задание {j['id']}: {j['status']} {err.get('code', '')} {err.get('message', '')}".strip())
    name = f"job-{j['id'][:8]}"
    if fmt == "json":
        return emit(as_json(j), out, f"{name}-json", full)
    emit(call("GET", f"/v1/transcriptions/{j['id']}", {"format": fmt}, raw=True), out, f"{name}-{fmt}", full)


def cmd_submit(a):
    body = {"audio_url": a.url, "summary": a.summary, "speakers": not a.no_speakers}
    if a.language:
        body["language"] = a.language
    if a.names:
        body["speaker_names"] = [n.strip() for n in a.names.split(",") if n.strip()]
    if a.external_id:
        body["external_id"] = a.external_id
    j = call("POST", "/v1/transcriptions", body=body, headers={"Idempotency-Key": uuid.uuid4().hex})
    eprint("поставлено: " + job_line(j))
    if not a.wait:
        eprint(f"результат: `diktuy.py job {j['id']} --wait`")
        return emit(j["id"])
    output_job(wait_job(j["id"], a.timeout), a.format, a.out, a.full)


def cmd_jobs(a):
    items = list(paged("/v1/transcriptions", {"status": a.status}, limit=a.limit))
    if a.json:
        return emit(as_json(items))
    emit("\n".join(job_line(j) for j in items) or "заданий нет (результаты хранятся 30 дней)")


def cmd_job(a):
    j = wait_job(a.id, a.timeout) if a.wait else call("GET", f"/v1/transcriptions/{a.id}")
    if j["status"] in ("queued", "processing"):
        return emit(job_line(j))
    output_job(j, a.format, a.out, a.full)


def cmd_speakers(a):
    speakers = []
    for pair in a.pairs:
        sid, sep, name = pair.partition("=")
        if not sep or not sid.isdigit():
            die(f"нужно НОМЕР=Имя, а пришло {pair!r}")
        speakers.append({"id": int(sid), "name": name or None})
    j = call("PATCH", f"/v1/transcriptions/{a.id}/speakers", body={"speakers": speakers})
    emit(", ".join(f"{s['id']}={s['name']}" for s in j["result"]["speakers"]))


def confirm(a, what):
    if not a.yes:
        die(f"{what} — необратимо. Спросите пользователя и повторите с флагом --yes", 2)


def cmd_cancel(a):
    confirm(a, f"отмена задания {a.id} и удаление результата")
    call("DELETE", f"/v1/transcriptions/{a.id}")
    emit(f"задание {a.id} отменено, результат удалён")


# ---------- уведомления (вебхуки) ----------

def cmd_webhooks(a):
    if a.action == "list":
        d = call("GET", "/v1/webhook-endpoints")
        lines = [f"{w['id']}  {'вкл ' if w['enabled'] else 'ВЫКЛ'}  {w['url']}  {','.join(w['events'])}"
                 + (f"  ({w['disabled_reason']})" if w.get("disabled_reason") else "")
                 + (f"  не принимает с {local(w['failing_since'])}" if w.get("failing_since") else "")
                 for w in d["data"]]
        return emit("\n".join(lines) or "адресов нет")
    if not a.arg:
        die(f"webhooks {a.action}: нужен {'URL' if a.action == 'add' else 'id адреса'}")
    if a.action == "add":
        body = {"url": a.arg}
        if a.events:
            body["events"] = a.events.split(",")
        if a.description:
            body["description"] = a.description
        w = call("POST", "/v1/webhook-endpoints", body=body)
        eprint("Секрет whsec_… показывается один раз — сразу сохраните его на сервере-получателе.")
        return emit(as_json(w))
    if a.action == "delete":
        confirm(a, f"удаление адреса уведомлений {a.arg}")
        call("DELETE", f"/v1/webhook-endpoints/{a.arg}")
        return emit(f"адрес {a.arg} удалён")
    if a.action == "test":
        call("POST", f"/v1/webhook-endpoints/{a.arg}/test")
        return emit("событие webhook.test уйдёт в течение минуты — итог: `diktuy.py webhooks deliveries <id>`")
    d = call("GET", f"/v1/webhook-endpoints/{a.arg}/deliveries")
    emit("\n".join(f"{local(x['created_at'])}  {x['event']:<26}  {x['status']:<8}  попыток {x['attempts']}  "
                   f"HTTP {x.get('last_http_status') or '—'}  {x.get('last_error') or ''}" for x in d["data"])
         or "доставок нет")


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", newline="\n")
    ap = argparse.ArgumentParser(prog="diktuy.py", description="Диктуй API: встречи, расшифровки, уведомления. "
                                 "Чтение бесплатно; transcribe и submit тратят кредиты (1 кредит = 1 минута записи).")
    ap.add_argument("--version", action="version", version=f"diktuy-skill {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def full_flag(s):
        s.add_argument("--full", action="store_true", help=f"длинный текст (> {INLINE_LIMIT} знаков) — в вывод, а не в файл")

    s = sub.add_parser("login", help="сохранить ключ API (спросит со скрытым вводом, проверит) в ~/.diktuy-skill/api-key")
    s.add_argument("--stdin", action="store_true", help="прочитать ключ из входного потока")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("logout", help="удалить сохранённый ключ с этого компьютера")
    s.set_defaults(fn=cmd_logout)

    s = sub.add_parser("me", help="аккаунт, тариф, кредиты, права ключа (бесплатно)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_me)

    s = sub.add_parser("meetings", help="встречи из приложения, новые сначала (бесплатно)")
    s.add_argument("--since", help="не старше: 7d, YYYY-MM-DD, ДД.ММ.ГГГГ")
    s.add_argument("--limit", type=int)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_meetings)

    s = sub.add_parser("meeting", help="одна встреча: выжимки, расшифровка, вопросы (бесплатно)")
    s.add_argument("ref", help="id | last | N (1 = последняя) | кусок названия или даты, напр. 28.10")
    s.add_argument("--format", choices=["markdown", "text", "json"], default="markdown",
                   help="markdown — выжимки и расшифровка (по умолчанию), text — только реплики, json — всё полями")
    s.add_argument("--summary", nargs="?", const="", metavar="ШАБЛОН",
                   help="только выжимки: short | tasks | protocol; без значения — все")
    s.add_argument("--questions", action="store_true", help="вопросы к встрече и ответы")
    s.add_argument("--out", help="записать в файл")
    full_flag(s)
    s.set_defaults(fn=cmd_meeting)

    s = sub.add_parser("search", help="поиск по говорящим, репликам, выжимкам и вопросам (бесплатно)")
    s.add_argument("query")
    s.add_argument("--since", default="30d", help="период: 30d (по умолчанию), 90d, YYYY-MM-DD, all")
    s.add_argument("--regex", action="store_true", help="query — регулярное выражение (без флага — с начала слова)")
    s.add_argument("--max", type=int, default=15, help="совпадений на встречу (по умолчанию 15)")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("tasks", help="задачи из выжимок «Задачи» всех встреч за период (бесплатно)")
    s.add_argument("--since", default="7d", help="период: 7d (по умолчанию), 30d, YYYY-MM-DD, all")
    s.add_argument("--out")
    full_flag(s)
    s.set_defaults(fn=cmd_tasks)

    s = sub.add_parser("transcribe", help="ПЛАТНО: файлы до 25 МБ / 30 мин → текст сразу")
    s.add_argument("files", nargs="+", help="файлы, шаблон *.ogg или папка")
    s.add_argument("--format", choices=["text", "json", "verbose_json", "srt", "vtt"], default="text")
    s.add_argument("--words", action="store_true", help="verbose_json с таймкодами слов")
    s.add_argument("--language", help="ru, en… (по умолчанию — определит сам)")
    s.add_argument("--prompt", help="имена и термины из записи, до 500 знаков")
    s.add_argument("--out", help="файл результата (для одного файла)")
    s.add_argument("--out-dir", help="папка результатов (для нескольких файлов)")
    full_flag(s)
    s.set_defaults(fn=cmd_transcribe)

    s = sub.add_parser("submit", help="ПЛАТНО: запись по ссылке (до 12 ч) → задание в очереди")
    s.add_argument("url", help="VK Видео, Rutube, Яндекс Диск, Google Диск, прямая https-ссылка на файл")
    s.add_argument("--summary", choices=["short", "protocol", "tasks", "none"], default="short")
    s.add_argument("--names", help="участники через запятую: «Иван Петров,Мария»")
    s.add_argument("--no-speakers", action="store_true", help="не делить по говорящим")
    s.add_argument("--language")
    s.add_argument("--external-id", help="своя метка, вернётся в ответах и уведомлениях")
    s.add_argument("--wait", action="store_true", help="дождаться и вывести результат")
    s.add_argument("--timeout", type=int, default=3600)
    s.add_argument("--format", choices=["markdown", "text", "srt", "vtt", "json"], default="markdown")
    s.add_argument("--out")
    full_flag(s)
    s.set_defaults(fn=cmd_submit)

    s = sub.add_parser("jobs", help="задания по ссылке, хранятся 30 дней (бесплатно)")
    s.add_argument("--status", help="через запятую: queued,processing,completed,failed,cancelled")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_jobs)

    s = sub.add_parser("job", help="статус задания, а когда готово — результат (бесплатно)")
    s.add_argument("id")
    s.add_argument("--format", choices=["markdown", "text", "srt", "vtt", "json"], default="markdown")
    s.add_argument("--wait", action="store_true")
    s.add_argument("--timeout", type=int, default=3600)
    s.add_argument("--out")
    full_flag(s)
    s.set_defaults(fn=cmd_job)

    s = sub.add_parser("speakers", help="имена говорящих в задании: 0=Иван 1=Мария (пусто — «Участник N»)")
    s.add_argument("id")
    s.add_argument("pairs", nargs="+")
    s.set_defaults(fn=cmd_speakers)

    s = sub.add_parser("cancel", help="отменить задание и БЕЗВОЗВРАТНО удалить результат")
    s.add_argument("id")
    s.add_argument("--yes", action="store_true", help="пользователь подтвердил")
    s.set_defaults(fn=cmd_cancel)

    s = sub.add_parser("webhooks", help="уведомления: list | add URL | delete ID | test ID | deliveries ID")
    s.add_argument("action", choices=["list", "add", "delete", "test", "deliveries"])
    s.add_argument("arg", nargs="?")
    s.add_argument("--events", help="через запятую; по умолчанию все")
    s.add_argument("--description")
    s.add_argument("--yes", action="store_true", help="для delete: пользователь подтвердил")
    s.set_defaults(fn=cmd_webhooks)

    a = ap.parse_args()
    try:
        a.fn(a)
    except ApiError as e:
        die(e.describe())
    except KeyboardInterrupt:
        die("прервано", 130)
    except BrokenPipeError:  # вывод обрезали через | head
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


if __name__ == "__main__":
    main()
