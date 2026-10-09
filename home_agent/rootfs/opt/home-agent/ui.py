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
    body += card_link("/assets", "🔧", "Utrustning", "Visa kopplade bilder och dokument")
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
        safe_id = esc(inbox_id)
        actions = ("<div class='sectionrow'><a class='text-link' target='_blank' rel='noopener' href='/inbox/file?id=%s'>Öppna original</a>"
                   "<form method='post' action='/inbox/dismiss' onsubmit='return confirm(&quot;Ta bort objektet från Inbox? Originalfilen bevaras.&quot;)'>"
                   "<input type='hidden' name='id' value='%s'><button type='submit'>Ta bort från Inbox</button></form></div>" % (safe_id, safe_id))
        body = body[:-10] + actions + "</article>"
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
    body += card_link("/assets", "🔧", "Utrustning", "Visa utrustningssidor")
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

def assets_page(rows):
    body = "<h1>Utrustning</h1><p class='sub'>Välj utrustning för att se bilder och dokument.</p>"
    for asset_id,name in rows:
        body += card_link("/asset?id="+quote(asset_id,safe=""),"🔧",name or "Utrustning","Visa detaljer och filer")
    if not rows:
        body += "<div class='card empty'>Ingen utrustning importerad ännu.</div>"
    return shell("Utrustning",body)

def asset_page(asset, files, candidates):
    if not asset:
        return shell("Saknas","<h1>Utrustningen hittades inte</h1><a href='/assets'>← Utrustning</a>")
    aid = quote(asset["id"],safe="")
    body = "<a class='text-link' href='/assets'>← Utrustning</a><p class='eyebrow'>UTRUSTNING</p><h1>%s</h1>" % esc(asset["name"] or "Utrustning")
    images = [(sid,name,media) for sid,name,media in files if (media or "").startswith("image/")]
    if images:
        sid,name,_ = images[0]
        body += "<div class='asset-hero'><a href='/source/file?asset=%s&amp;id=%s' target='_blank' rel='noopener'><img alt='%s' src='/source/file?asset=%s&amp;id=%s'></a></div>" % (aid,quote(sid,safe=""),esc(name or "Bild"),aid,quote(sid,safe=""))
    body += "<h2>Bilder &amp; dokument</h2>"
    if images:
        body += "<div class='asset-gallery'>"
        for sid,name,_ in images[:4]:
            url = "/source/file?asset=%s&amp;id=%s" % (aid,quote(sid,safe=""))
            body += "<a href='%s' target='_blank' rel='noopener'><img loading='lazy' src='%s' alt='%s'></a>" % (url,url,esc(name or "Bild"))
        body += "</div>"
    if not files:
        body += "<div class='card empty'>Inga kopplade filer ännu.</div>"
    for sid,name,media in files:
        url = "/source/file?asset=%s&amp;id=%s" % (aid,quote(sid,safe=""))
        body += "<a class='card line card-link' target='_blank' rel='noopener' href='%s'><span class='ico'>%s</span><span class='grow'><strong class='name'>%s</strong><small class='muted'>%s</small></span><span class='arrow'>↗</span></a>" % (url,"🖼️" if (media or "").startswith("image/") else "📄",esc(name or "Namnlös fil"),esc(media or "Fil"))
    body += ("<details class='card'><summary>+ Ladda upp fil</summary>"
             "<form class='upload' action='/asset/upload' method='post' enctype='multipart/form-data'>"
             "<input type='hidden' name='asset_id' value='%s'><input type='file' name='source' required>"
             "<button type='submit'>Spara och koppla</button></form></details>" % esc(asset["id"]))
    body += ("<details class='card'><summary>+ Importera från Google Drive</summary>"
             "<p>Importera en fil från den godkända delade mappen.</p>"
             "<form method='post' action='/asset/drive-import'>"
             "<input type='hidden' name='asset_id' value='%s'>"
             "<label for='drive_file_id'>Google Drive fil-ID</label>"
             "<input id='drive_file_id' name='drive_file_id' required autocomplete='off'>"
             "<button type='submit'>Importera och koppla</button></form></details>" % esc(asset["id"]))
    linked = {sid for sid,_,_ in files}
    available = [(sid,name,media) for sid,name,media in candidates if sid not in linked]
    if available:
        body += ("<details class='card'><summary>+ Koppla befintlig fil</summary>"
                 "<form method='post' action='/asset/link'><input type='hidden' name='asset_id' value='%s'>"
                 "<label for='source_id'>Fil i lokalt arkiv</label><select name='source_id' id='source_id'>" % esc(asset["id"]))
        for sid,name,media in available:
            body += "<option value='%s'>%s</option>" % (esc(sid),esc(name or sid))
        body += "</select><button type='submit'>Koppla fil</button></form></details>"
    body += "<details class='card technical'><summary>Tekniska detaljer</summary><pre>%s</pre></details>" % esc(__import__("yaml").safe_dump(asset["data"],allow_unicode=True,sort_keys=False))
    return shell(asset["name"] or "Utrustning",body)
