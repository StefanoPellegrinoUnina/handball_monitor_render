# Deploy su Render — guida rapida

## 1. GitHub

Decomprimi il pacchetto. Nel repository GitHub devi vedere direttamente:

```text
app.py
scraper.py
db.py
requirements.txt
render.yaml
.python-version
templates/
static/
```

Non mettere la cartella intera dentro un'ulteriore sottocartella, a meno di configurare `rootDir` su Render.

## 2. Render

1. Accedi a Render.
2. `New` → `Blueprint`.
3. Collega GitHub e scegli il repository.
4. Lascia come Blueprint path `render.yaml`.
5. Controlla che venga creato **handball-monitor-italia** come Web Service Python.
6. Conferma il deploy.

Il Blueprint usa Frankfurt, una singola istanza e un Persistent Disk da 1 GB montato in `/var/data`.

## 3. Controlli dopo il deploy

Apri:

```text
https://TUO-SITO.onrender.com/healthz
```

Devi vedere qualcosa simile a:

```json
{"ok":true,"database":"/var/data/handball.sqlite3","matches":0}
```

Subito dopo il primo avvio parte un primo sync in background. Il numero `matches` crescerà quando i dati vengono acquisiti.

Poi apri la homepage. Se vuoi forzare il controllo usa **Aggiorna FIGH**.

## 4. Backup

Premi **Esporta backup**. Il browser scarica un JSON contenente gare, partecipanti, sanzioni, designazioni, problemi di qualità e storico dei sync.

## 5. Se il deploy fallisce

Controlla `Logs` su Render. Le cause più comuni sono:

- file caricati in una sottocartella e `render.yaml` non trovato;
- build interrotta durante `pip install -r requirements.txt`;
- servizio creato come Static Site invece che Python Web Service;
- Persistent Disk non creato/compatibile col piano scelto;
- FIGH temporaneamente non raggiungibile: la webapp resta online e l'errore compare in Data Quality.
