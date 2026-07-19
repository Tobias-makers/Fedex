# FedEx priskoll — sista minuten-pris (International Economy)

Automatisk bevakning av FedEx "FAST SISTA MINUTEN-PRIS" för International Economy®
på rutten **Sverige 52390 → Middletown, PA 17057, USA** (10 kolli à 18 kg, 60×40×20 cm).

Körs helt i GitHubs moln två gånger om dagen — din dator behöver inte vara på.

## Så funkar det

- `scrape.py` — öppnar FedEx öppna prisverktyg i en headless webbläsare (Playwright),
  fyller i uppgifterna och läser av sista minuten-priset för Economy.
- `.github/workflows/priskoll.yml` — kör scriptet 08:00 och 16:00 svensk sommartid
  (06:00/14:00 UTC) och sparar varje mätning i `docs/history.json`.
- `docs/index.html` — dashboard (pris/kg, totalpris, graf, historik) som publiceras
  med GitHub Pages.

## Kom igång (engångssteg)

1. **Aktivera Pages:** Settings → Pages → under "Branch": välj `main` och mappen
   `/docs` → Save. Efter någon minut finns dashboarden på
   `https://<ditt-användarnamn>.github.io/<repo-namn>/`
2. **Testkör direkt:** fliken Actions → "FedEx priskoll" i vänsterlistan →
   knappen "Run workflow" → Run workflow. Efter ca 2–3 minuter ska körningen bli
   grön och en ny mätpunkt synas på dashboarden.
3. Klart — schemat sköter resten automatiskt.

## Om en körning blir röd

Öppna den röda körningen under Actions. Längst ner under "Artifacts" finns
`debug-…` med en screenshot (`fel.png`) och sidans text (`sidtext.txt`) som visar
exakt var det gick fel. Vanligaste orsaken är att FedEx botskydd blockerat
GitHubs IP-adress just då — misslyckas körningarna konsekvent behövs en annan
lösning för webbläsardelen (t.ex. en browser-tjänst).

## Ändra rutt eller kolli

Öppna `scrape.py` och ändra konstanterna högst upp (`FROM_POSTAL`, `TO_QUERY`,
`TO_SUGGESTION`, `PACKAGES`, `WEIGHT`, `DIMS`). Ändra tider i
`.github/workflows/priskoll.yml` (cron är i UTC).
