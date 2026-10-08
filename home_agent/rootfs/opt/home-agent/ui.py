"""Mobile-first presentation only. Domain operations stay in server.py."""
import html
from urllib.parse import quote

def esc(value):
    return html.escape(str(value if value is not None else ""))

def shell(title, body, active="home", notice=None, error=None):
    tabs = [("/", "⌂", "Hem", "home"), ("/todo", "☑", "Att göra", "todo"),
            ("/add", "+", "Lägg till", "add"), ("/search", "⌕", "Sök", "search"),
            ("/more", "☰", "Mer", "more")]
    nav = "".join("<a class='tab %s %s' href='%s'><b>%s</b><span>%s</span></a>" %
                  ("active" if active == key else "", "add-tab" if key == "add" else "",
                   path, symbol, label) for path, symbol, label, key in tabs)
    alerts = ("<div class='alert'>%s</div>" % esc(notice) if notice else "") + (
        "<div class='alert error'>%s</div>" % esc(error) if error else "")
    return ("<!doctype html><html lang='sv'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<meta name='color-scheme' content='light dark'><title>%s · Home Agent</title>"
            "<link rel='stylesheet' href='/ui.css'></head><body><div class='app'>"
            "<header class='top'><a class='brand' href='/'>⌂ HOME AGENT</a>"
            "<span class='avatar'>HA</span></header><main class='content'>%s%s</main>"
            "<nav class='nav' aria-label='Huvudnavigation'>%s</nav></div></body></html>" %
            (esc(title), alerts, body, nav)).encode("utf-8")

def card_link(path, icon, title, subtitle, arrow=True):
    return ("<a class='card line card-link' href='%s'><span class='ico'>%s</span>"
            "<span class='grow'><strong class='name'>%s</strong><small class='muted'>%s</small></span>%s</a>" %
            (path, icon, esc(title), esc(subtitle), "<span class='arrow'>→</span>" if arrow else ""))

def room_groups(home):
    floors = home.get("floors", []) if home else []
    if isinstance(floors, dict):
        floors = list(floors.values())
    for floor in floors or []:
        rooms = floor.get("rooms", [])
        if isinstance(rooms, dict):
            rooms = list(rooms.values())
        yield floor, rooms or []

def home_page(data, inbox_count, notice=None, error=None):
    home = None
    if isinstance(data, dict):
        homes = data.get("homes", [])
        if isinstance(homes, list) and homes:
            home = homes[0]
        elif isinstance(homes, dict) and homes:
            home = next(iter(homes.values()))
    name = (home or {}).get("name", "Mitt hem")
    room_count = sum(len(rooms) for _, rooms in room_groups(home))
    body = ("<p class='eyebrow'>DIN HUSÖVERSIKT</p><h1>Välkommen hem</h1>"
            "<p class='sub'>Ditt hem, samlat på ett ställe.</p>"
            "<div class='hero'><small>MITT HEM</small><h2>%s</h2>"
            "<p>%s rum och utrymmen finns i Home Agent.</p>"
            "<a class='hero-btn' href='/rooms'>Utforska hemmet →</a></div>"
            "<div class='actions'><a class='action' href='/inbox'><span>📥</span><strong>Inbox</strong>"
            "<small>%s väntar</small></a><a class='action' href='/add'><span>＋</span>"
            "<strong>Lägg till</strong><small>Bild eller dokument</small></a></div>"
            "<div class='sectionrow'><h2>Överblick</h2><a class='text-link' href='/todo'>Visa att göra →</a></div>" %
            (esc(name), room_count, inbox_count))
    body += card_link("/inbox", "📥", "%s filer i Inbox" % inbox_count, "Sparade lokalt · väntar på analys")
    body += card_link("/rooms", "🏠", "Rum och utrymmen", "Utforska hemstrukturen")
    if not home:
        body += "<p class='sub'>Ingen hemstruktur importerad ännu.</p>"
    return shell("Hem", body, notice=notice, error=error)

def rooms_page(data):
    home = None
    if isinstance(data, dict):
        homes = data.get("homes", [])
        home = (homes[0] if isinstance(homes, list) and homes else
                next(iter(homes.values())) if isinstance(homes, dict) and homes else None)
    body = "<h1>Mitt hem</h1><p class='sub'>Utforska rum och utrymmen.</p>"
    for floor, rooms in room_groups(home):
        body += "<h2>%s</h2><div class='roomgrid'>" % esc(floor.get("name", "Våning"))
        for room in rooms:
            body += ("<a class='card room-card' href='/room?id=%s'><span class='room-icon'>⌂</span>"
                     "<strong class='name'>%s</strong><small class='muted'>Visa rum →</small></a>" %
                     (quote(str(room.get("id", ""))), esc(room.get("name", "Rum"))))
        body += "</div>"
    return shell("Rum", body)

def inbox_page(rows, queue_state=None):
    count = sum(1 for r in rows if r[3] in ("pending", "paused", "failed"))
    body = ("<h1>Inbox</h1><p class='sub'>Här samlas nytt material innan det bearbetas.</p>"
            "<div class='sectionrow'><span class='pill'>%s väntar</span>"
            "<a class='text-link' href='/add'>+ Lägg till</a></div>"
            "<div class='info-card'><strong>Teknisk kontroll av original</strong>"
            "<p>Originalen är sparade lokalt. Arbetskön verifierar filer; AI-analys kommer senare.</p>"
            "<span class='pill gray'>AI-analys kommer senare</span></div>" % count)
    if queue_state:
        control, counts = queue_state
        body += ("<div class='card'><strong>Teknisk förbehandling</strong>"
                 "<p>Kontrollerar sparade originalfiler. Semantisk AI-analys ingår inte.</p>"
                 "<p>Kö: %s · Väntande: %s · Pågår: %s · Väntar på AI: %s · Fel: %s</p>"
                 "<form method='post' action='/inbox/%s'><button type='submit'>%s</button></form>"
                 "</div>" % (esc(control), counts.get('pending',0), counts.get('processing',0),
                            counts.get('awaiting_ai',0), counts.get('failed',0),
                            'resume' if control == 'paused' else 'pause' if control == 'running' else 'analyze',
                            'Återuppta analys' if control == 'paused' else 'Pausa analys' if control == 'running' else 'Analysera Inbox'))
    if not rows:
        body += "<div class='card empty'>Inbox är tom. <a href='/add'>Lägg till en fil</a>.</div>"
    for inbox_id, created, stage, status, filename, media, source_id, channel, occurrence_id in rows:
        label = "Bild" if (media or "").startswith("image/") else "Dokument" if media else "Fil"
        icon = "🖼️" if label == "Bild" else "📄"
        status_label = {"pending":"Väntar på analys","paused":"Pausad","failed":"Behöver åtgärd","awaiting_ai":"Tekniskt kontrollerad · väntar på AI","processing":"Kontrolleras"}.get(status, "Under behandling")
        body += ("<article class='card'><div class='line'><span class='ico'>%s</span>"
                 "<div class='grow'><strong class='name'>%s</strong>"
                 "<small class='muted'>%s · %s</small></div></div>"
                 "<div class='divider'></div><div class='sectionrow'><span class='pill'>%s</span>"
                 "<details><summary>Detaljer ⌄</summary><div class='detail'>"
                 "Steg: %s · Status: %s<br>Kanal: %s<br>InboxItem: %s<br>Source: %s"
                 "<br>IngestOccurrence: %s</div></details></div></article>" %
                 (icon, esc(filename or "Namnlös fil"), label, esc(created), esc(status_label),
                  esc(stage), esc(status), esc(channel), esc(inbox_id), esc(source_id), esc(occurrence_id)))
    return shell("Inbox", body, "home")

def add_page():
    body = ("<h1>Lägg till</h1><p class='sub'>Spara foto eller dokument till Home Agent.</p>"
            "<div class='card'><div class='line'><span class='ico'>📎</span>"
            "<div><strong class='name'>Foto eller dokument</strong>"
            "<small class='muted'>Originalet sparas lokalt först</small></div></div>"
            "<form class='upload' method='post' action='/capture' enctype='multipart/form-data'>"
            "<input type='file' name='source' required><button type='submit'>Spara i Inbox</button>"
            "</form></div><div class='card'><strong>Analysera nu</strong>"
            "<p class='sub'>Aktiveras när analysmotorn finns. Inga AI-åtgärder körs ännu.</p>"
            "<span class='pill gray'>Kommer senare</span></div>")
    return shell("Lägg till", body, "add")

def todo_page(count):
    body = "<h1>Att göra</h1><p class='sub'>Saker som väntar på din uppmärksamhet.</p>"
    body += card_link("/inbox", "📥", "%s filer i Inbox" % count, "Väntar på framtida analys")
    body += "<div class='card empty'>Underhåll och uppföljningar kommer senare.</div>"
    return shell("Att göra", body, "todo")

def search_page():
    return shell("Sök", "<h1>Sök</h1><p class='sub'>Sökning kopplas till verkliga data senare.</p>"
                 "<div class='card empty'>Sökfunktionen är inte aktiv ännu.</div>", "search")

def more_page():
    body = "<h1>Mer</h1><p class='sub'>Fler vyer och verktyg.</p>"
    body += card_link("/rooms", "🏠", "Rum och utrymmen", "Visa alla rum")
    body += card_link("/inbox", "📥", "Inbox", "Visa sparade filer")
    body += "<details class='card'><summary>Importera YAML (avancerat)</summary>"
    body += ("<form method='post' action='/import' enctype='multipart/form-data'>"
             "<input type='file' name='snapshot' accept='.yaml,.yml,text/yaml,application/x-yaml' required>"
             "<button type='submit'>Importera</button></form></details>")
    body += "<p class='foot'>Home Agent · Lokal lagring</p>"
    return shell("Mer", body, "more")

def room_detail_page(room_id, floor, room, sections, history):
    """Render already-resolved explicit relationships, never infer room links."""
    if not room:
        return shell("Rum saknas", "<h1>Rummet hittades inte</h1><p><a href='/rooms'>← Alla rum</a></p>")
    body = ("<a class='text-link' href='/rooms'>← Alla rum</a>"
            "<p class='eyebrow room-eyebrow'>RUM</p><h1>%s</h1>"
            "<p class='sub'>%s</p>" % (esc(room.get("name", room_id)), esc(floor.get("name", ""))))
    notes = room.get("notes") or []
    if isinstance(notes, str):
        notes = [notes] if notes.strip() else []
    notes_count = len(notes) if isinstance(notes, list) else 0
    equipment_count = sum(len(sections.get(key, [])) for key in ("System", "Utrustning", "Komponenter"))
    body += ("<div class='actions room-stats'><a class='action' href='#notes'><span>📝</span>"
             "<strong>Anteckningar</strong><small>%s st</small></a>"
             "<a class='action' href='#related'><span>🔧</span>"
             "<strong>System & utrustning</strong><small>%s kopplingar</small></a></div>" %
             (notes_count, equipment_count))
    body += "<div class='sectionrow' id='notes'><h2>Anteckningar</h2></div>"
    body += "<section class='card room-section'>"
    if notes_count:
        for note in reversed(notes):
            if isinstance(note, dict):
                value, stamp = note.get("text", ""), note.get("created_at", "")
            else:
                value, stamp = str(note), ""
            body += "<div class='note'><p>%s</p>%s</div>" % (
                esc(value), "<small class='muted'>%s</small>" % esc(stamp) if stamp else "")
    else:
        body += "<p class='sub'>Inga anteckningar ännu.</p>"
    body += ("<details class='note-add'><summary>+ Lägg till anteckning</summary>"
             "<form class='room-note-form' method='post' action='/add-note'>"
             "<input type='hidden' name='room_id' value='%s'>"
             "<label for='note'>Ny anteckning</label>"
             "<textarea id='note' name='note' rows='3' required maxlength='5000'></textarea>"
             "<button type='submit'>Spara anteckning</button></form></details></section>" % esc(room_id))
    body += "<h2 id='related'>Relaterat till rummet</h2>"
    any_related = False
    for title, items in sections.items():
        if not items:
            continue
        any_related = True
        body += "<section class='card room-section'><strong>%s</strong><ul class='related-list'>" % esc(title)
        for item in items:
            body += "<li>%s</li>" % esc(item.get("name") or item.get("id") or "Namnlöst objekt")
        body += "</ul></section>"
    if not any_related:
        body += "<div class='card empty'>Inga kopplade objekt ännu.</div>"
    if history:
        body += "<h2>Ändringshistorik</h2><section class='card room-section'>"
        for committed_at, field_name, old_value, new_value in history:
            body += ("<div class='note'><small class='muted'>%s · %s</small>"
                     "<p>%s</p></div>" % (esc(committed_at), esc(field_name), esc(new_value)))
        body += "</section>"
    body += ("<details class='card technical'><summary>Tekniska detaljer</summary>"
             "<p class='sub'>Rådata och interna fält visas separat från rummets vanliga information.</p>"
             "<pre>%s</pre></details>" % esc(__import__("yaml").safe_dump(room, allow_unicode=True, sort_keys=False)))
    return shell(str(room.get("name", "Rum")), body)
