# Handball Monitor Italia — Render edition

Dashboard stagionale per **Serie A Gold maschile** e **Serie A1 femminile**.

Questa versione è predisposta per essere pubblicata come **Web Service Python su Render** e, in produzione, usa un **Persistent Disk** per non perdere il database SQLite ai redeploy/restart.

## Funzioni

- lettura calendari ufficiali FIGH;
- individuazione dei Match Report ufficiali;
- estrazione dei referti PDF con reti individuali, ammonizioni, esclusioni da 2', squalifiche e sanzioni alla panchina;
- arbitri, coppie arbitrali, commissari/delegati;
- archivio cumulativo per gara, squadra, giocatore e ufficiale;
- pannello Data Quality per errori/referti mancanti;
- sincronizzazione automatica configurabile;
- pulsante **Aggiorna FIGH** per una sincronizzazione manuale;
- **Esporta backup** per scaricare l'intero archivio in JSON.

## Deploy consigliato: Render + Persistent Disk

Il file `render.yaml` configura automaticamente:

- Web Service Python in regione Frankfurt;
- una sola istanza;
- health check `/healthz`;
- database in `/var/data/handball.sqlite3`;
- Persistent Disk da 1 GB;
- timezone `Europe/Rome`;
- sync automatico alle 23:10 e 07:15 ogni giorno;
- prima sincronizzazione automatica se il database è vuoto.

### Passi

1. Crea un repository GitHub vuoto.
2. Carica **il contenuto di questa cartella nella root del repository**. `render.yaml` deve trovarsi nella root.
3. Su Render scegli **New → Blueprint**.
4. Collega il repository GitHub.
5. Render rileverà `render.yaml`: controlla il riepilogo e crea il Blueprint.
6. Attendi build e deploy.
7. Apri l'URL `*.onrender.com` assegnato al servizio.
8. Controlla `/healthz`: deve restituire `{"ok": true, ...}`.
9. Se la prima sincronizzazione non è ancora terminata, attendi qualche minuto o premi **Aggiorna FIGH**.

> La configurazione con Persistent Disk richiede un servizio Render compatibile con i dischi persistenti. È la configurazione consigliata per uno studio che deve durare per tutta la stagione.

## Variante gratuita solo per prova

`render-free.example.yaml` mostra una configurazione di test senza Persistent Disk. **Non usarla come archivio stagionale**: il filesystem può essere eliminato a restart/redeploy e quindi il database può andare perso.

## Avvio locale

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Apri `http://127.0.0.1:8000`.

Per evitare il sync automatico durante test locali:

```bash
DISABLE_SCHEDULER=1 AUTO_SYNC_ON_EMPTY_DB=0 uvicorn app:app --reload
```

## Variabili ambiente

- `HANDBALL_DB_PATH`: percorso del database SQLite. Default `./data/handball.sqlite3`.
- `APP_TIMEZONE`: default `Europe/Rome`.
- `SYNC_TIMES`: orari separati da virgola, default `23:10,07:15`.
- `SYNC_DAYS`: `*` per tutti i giorni oppure numeri `0..6` (0=lunedì, 6=domenica).
- `AUTO_SYNC_ON_EMPTY_DB`: `1` per fare un primo popolamento quando il DB è vuoto.
- `DISABLE_SCHEDULER`: `1` per disattivare lo scheduler interno.

## Endpoint principali

- `GET /healthz` — health check e numero di gare in DB
- `POST /api/sync` — sincronizzazione FIGH immediata
- `GET /api/matches` — gare
- `GET /api/team-stats` — statistiche squadre
- `GET /api/players` — giocatori
- `GET /api/sanctions` — sanzioni
- `GET /api/pairs` — coppie arbitrali e delegati
- `GET /api/issues` — anomalie/data quality
- `GET /api/export-json` — backup completo scaricabile
- `POST /api/import-report` — import manuale di un referto PDF
- `POST /api/import-json` — import strutturato JSON

## Persistenza

SQLite è adatto a questo progetto personale perché il traffico è basso e una singola istanza è sufficiente. Su Render il DB viene scritto sotto `/var/data`, cioè dentro il Persistent Disk. Il resto del filesystem può essere effimero senza problemi.

## Nota sullo scheduler

Lo scheduler gira **dentro la stessa Web Service** che possiede il disco SQLite. Questo evita il problema di condividere un file SQLite tra servizi diversi. Per intercettare anticipi/posticipi insoliti è impostato di default due volte al giorno, non soltanto mercoledì/sabato/domenica.

## Verifica parser

I referti FIGH sono PDF tabellari e il parser usa `pdfplumber`. Se il layout federale cambia, l'errore viene registrato in **Data quality** invece di inventare valori. Prima di usare i dati per analisi definitive conviene comunque fare controlli a campione sui referti originali.
