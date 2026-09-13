# CraftBeerPi UI 0.5.0 – BeerXML-Dropdown bleibt leer

## Umgebung

- CraftBeerPi Server: 4.7.4
- CraftBeerPi UI: 0.5.0
- Python: 3.13.5
- OS: Debian 13 (Trixie), 64 Bit
- Raspberry Pi 3 Model B
- Browser: Chromium / Firefox

## Fehlerbild

Nach dem erfolgreichen Upload einer gültigen BeerXML-Datei blieb das Dropdown **„BeerXML Recipe from uploaded file“** leer.

Der Upload selbst war erfolgreich, und das Backend konnte die Datei korrekt lesen.

Test:

```bash
curl http://127.0.0.1:8000/upload/xml
```

Antwort:

```json
[{"value": "1", "label": "American IPA"}]
```

Auch der direkte Aufruf von

```text
http://<CBPI-IP>:8000/upload/xml
```

im Browser eines anderen Rechners lieferte die korrekte JSON-Antwort.

Damit waren folgende Teile als funktionierend bestätigt:

1. BeerXML-Datei
2. Upload nach CraftBeerPi
3. XML-Parser im Backend
4. Endpoint `GET /upload/xml`
5. Netzwerkzugriff vom Browser

Der Fehler lag ausschließlich in der Weboberfläche.

## Reproduktion

1. CraftBeerPi-Seite **Recipe Upload** öffnen.
2. Eine gültige BeerXML-Datei hochladen.
3. CraftBeerPi meldet den Upload als erfolgreich.
4. Das Dropdown **„BeerXML Recipe from uploaded file“** bleibt leer.
5. Gleichzeitig liefert `/upload/xml` das Rezept korrekt zurück.
6. Browser-Neuladen bzw. `Strg+F5` behebt den Fehler nicht.

## Ursache

Im minifizierten JavaScript der CraftBeerPi UI 0.5.0 wurde der Wert des BeerXML-Single-Selects als leeres Array initialisiert:

```javascript
[v,y]=(0,n.useState)([])
```

Der betreffende Select ist aber ein normaler Single-Select. Nach Änderung des Initialwerts auf einen leeren String funktioniert das Dropdown:

```javascript
[v,y]=(0,n.useState)("")
```

Die betroffene Datei der installierten UI war:

```text
/home/wallbox/.local/share/pipx/venvs/cbpi4/lib/python3.13/site-packages/cbpi4gui/build/static/js/main.65b608fc.js
```

## Verifizierter Workaround

Vor der Änderung wurde eine Sicherung angelegt:

```bash
cp /home/wallbox/.local/share/pipx/venvs/cbpi4/lib/python3.13/site-packages/cbpi4gui/build/static/js/main.65b608fc.js \
   /home/wallbox/.local/share/pipx/venvs/cbpi4/lib/python3.13/site-packages/cbpi4gui/build/static/js/main.65b608fc.js.bak
```

Anschließend wurde exakt der Initialwert geändert:

```bash
sed -i 's/\[v,y\]=(0,n\.useState)(\[\])/\[v,y\]=(0,n.useState)("")/' \
/home/wallbox/.local/share/pipx/venvs/cbpi4/lib/python3.13/site-packages/cbpi4gui/build/static/js/main.65b608fc.js
```

Kontrolle:

```bash
grep -o '\[v,y\]=(0,n.useState)([^;]*' \
/home/wallbox/.local/share/pipx/venvs/cbpi4/lib/python3.13/site-packages/cbpi4gui/build/static/js/main.65b608fc.js
```

Erwarteter Treffer:

```text
[v,y]=(0,n.useState)("")
```

Nach einem Hard-Reload des Browsers (`Strg+F5`) erschien das BeerXML-Rezept korrekt im Dropdown.

Anschließend funktionierte auch **„Create Recipe from BeerXML Recipe“** erfolgreich.

## Ergebnis

Der native CraftBeerPi-Import funktioniert mit:

```text
RECIPE_CREATION_PATH = upload
```

Das zusätzliche Plugin `cbpi4-RecipeImport` ist dafür nicht erforderlich.

Nach erfolgreicher Reparatur wurde `cbpi4-RecipeImport` wieder entfernt.

## GitHub-Issue

Der Fehler wurde im offiziellen UI-Repository gemeldet:

- Repository: `PiBrewing/craftbeerpi4-ui`
- Issue: **#76**
- Titel: **BeerXML recipe dropdown stays empty in UI 0.5.0 due to Select value initialized as array**

## Hinweise

- Der lokale Patch kann durch ein späteres Update von `cbpi4gui` überschrieben werden.
- Nach einem UI-Update sollte geprüft werden, ob Issue #76 upstream behoben wurde.
- Die hochgeladene BeerXML-Datei wird von CraftBeerPi unter `config/upload/beer.xml` gespeichert und beim nächsten BeerXML-Upload ersetzt.
