# drszentgyorgyi.hu – statikus másolat

A [www.drszentgyorgyi.hu](https://www.drszentgyorgyi.hu/index.php) (Joomla alapú)
iskolai honlap **egy az egyben statikus másolata**, hogy olcsón hostolható legyen
**Cloudflare Pages**-en. A teljes kész weboldal a [`public/`](public/) mappában van.

## Tartalom

- `public/` – a kész, statikus weboldal (ezt szolgálja ki a Cloudflare Pages)
  - HTML oldalak tiszta URL-eken (pl. `/etkezes/`, `/bemutatkozunk/`)
  - `templates/`, `media/`, `plugins/`, `images/` – CSS, JS, képek
  - `attachments/` – letöltött PDF dokumentumok (ékezetes fájlnevekkel)
  - `_redirects` – a régi `index.php/...` URL-ek átirányítása a tiszta URL-ekre
- `crawl.py` – a letöltő/másoló szkript (újrafuttatható, ha frissül az eredeti)
- `crawl_extras.py` – 2. fázis: nyomtatási nézetek (`.../print/`) és RSS/Atom feedek
- `fix_pagination.py` – a Joomla blog-lapozás statikussá alakítása (lásd lentebb)

## Deploy Cloudflare Pages-re

1. Cloudflare dashboard → **Workers & Pages** → **Create application** → **Pages**
   → **Connect to Git** → válaszd ezt a repót (`Blextor/gyorgyialbi`).
2. Build beállítások:
   - **Framework preset:** `None`
   - **Build command:** *(üresen hagyni)*
   - **Build output directory:** `public`
3. **Save and Deploy.** Minden git push automatikusan újra deployol.

Saját domaint a Pages projekt **Custom domains** fülén lehet hozzáadni.

### Helyi kipróbálás

```bash
cd public
python -m http.server 8000
# majd: http://localhost:8000/
```

## Lapozás (Joomla blog pagination)

Néhány kategória több cikket listáz lapozóval (eredetileg `?start=N` query-vel,
ami statikusan nem működik). Ezek **több statikus oldalra** lettek bontva, a
lapozó megtartásával és a lapok kereszt-összekötésével:

| Kategória | 1. oldal | 2. oldal |
|---|---|---|
| Gyermekvédelem | `/gyermekvedelem/` | `/gyermekvedelem/2/` |
| Beiratkozás | `/beiratkozas/` | `/beiratkozas/2/` |
| Eredményeink | `/eredmenyeink/` | `/eredmenyeink/2/` |

A „Tovább/Utolsó/2" gombok a `/…/2/`, az „Első/Előző/1" gombok a `/…/` oldalra
mutatnak. (A régi `?start=N` linkek a `_redirects` miatt az 1. oldalra esnek.)

## A másolat frissítése

```bash
python crawl.py            # 1) teljes letöltés az élő oldalról
python crawl_extras.py     # 2) nyomtatási nézetek + feedek
python fix_pagination.py   # 3) lapozós kategóriák statikus szétbontása
```

## Megjegyzések

- A külső szolgáltatások (Google Fonts, addtoany, Facebook, e-Kréta, Office Forms
  linkek) szándékosan az eredeti forrásukra mutatnak – ezek nem részei a másolatnak.
- A `meta canonical` / `og:url` tag-ek az eredeti oldallal egyezően maradtak;
  saját domain használata esetén ezek cserélhetők.
- A nyomtatási nézetek (`.../print/`) és az RSS/Atom feedek (`feeds/*.xml`) is le
  lettek mentve statikusan, és a linkek ezekre mutatnak.
- Néhány hivatkozás **már az eredeti oldalon is 404-es** (törött az eredeti
  tartalomban), ezért a másolatból is hiányzik – ezek nem voltak letölthetők:
  - `dok/prevencio/kamasz.pdf`, `dok/prevencio/aldozat.pdf`,
    `dok/prevencio/Figyelemfelhívás-Kék bálna.pdf`
  - `dok/brfk/...` covid-tájékoztató képek és PDF (6 db)
  - `templates/dd_schoolsfun_48/images/{tumblr,vimeo,youtube}icon.png`
    (a sablon hivatkozik rájuk, de soha nem voltak feltöltve)
- A teljes másolat ellenőrizve: 6775 belső hivatkozásból csak a fenti, eredetin is
  törött 12 hiányzik; minden más oldal, kép, PDF, CSS/JS és feed letöltve.