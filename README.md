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

## A másolat frissítése

```bash
python crawl.py          # újraírja a public/ tartalmát az élő oldalról
```

## Megjegyzések

- A külső szolgáltatások (Google Fonts, addtoany, Facebook, e-Kréta, Office Forms
  linkek) szándékosan az eredeti forrásukra mutatnak – ezek nem részei a másolatnak.
- A `meta canonical` / `og:url` tag-ek az eredeti oldallal egyezően maradtak;
  saját domain használata esetén ezek cserélhetők.
- Két, már az eredeti oldalon is hiányzó (404-es) PDF nem volt letölthető:
  `dok/prevencio/kamasz.pdf`, `dok/prevencio/aldozat.pdf`.
