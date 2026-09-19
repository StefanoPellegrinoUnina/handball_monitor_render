# Deploy gratuito — Render + Neon + GitHub Actions

Questa è la procedura consigliata per evitare il Persistent Disk a pagamento di Render.

## 1. Aggiorna il repository GitHub

Sostituisci i file del repository con il contenuto di questa cartella e fai **Commit changes**.

Controlla che `render.yaml` sia nella root del repository, allo stesso livello di `app.py`.

La nuova configurazione contiene:

```yaml
plan: free
```

e non contiene più `disk:`.

## 2. Crea il database gratuito su Neon

1. Crea un account Neon e un nuovo progetto PostgreSQL.
2. Nel progetto apri **Connect** / **Connection Details**.
3. Copia la connection string PostgreSQL completa. Deve assomigliare a:

```text
postgresql://utente:password@host/database?sslmode=require
```

Non pubblicare questa stringa su GitHub: contiene la password del database.

Non devi creare tabelle a mano. La webapp crea automaticamente lo schema al primo avvio.

## 3. Torna su Render

Se eri fermo sulla finestra di pagamento, chiudila.

Dopo il commit del nuovo `render.yaml`:

1. torna al Blueprint;
2. fai **Retry** / **Manual Sync**;
3. Render dovrebbe riconoscere un solo **Web Service Free** e nessun disco;
4. quando chiede `DATABASE_URL`, incolla la connection string Neon;
5. avvia il deploy.

`SYNC_TOKEN` viene generato automaticamente da Render.

## 4. Verifica il deploy

Quando Render ha terminato, apri:

```text
https://TUO-SITO.onrender.com/healthz
```

Dovresti vedere qualcosa del tipo:

```json
{"ok":true,"database":"PostgreSQL","matches":0}
```

Subito dopo il primo avvio la webapp prova anche una prima sincronizzazione FIGH se il database è vuoto.

## 5. Attiva gli aggiornamenti automatici con GitHub Actions

Render Free può andare in sleep. Per questo il progetto include:

```text
.github/workflows/sync-figh.yml
```

Il workflow chiama la webapp da GitHub e la sveglia prima di sincronizzare.

### A. Recupera SYNC_TOKEN da Render

Apri:

**Render → handball-monitor-italia → Environment**

Copia il valore di `SYNC_TOKEN`.

### B. Crea due GitHub Secrets

Nel repository:

**Settings → Secrets and variables → Actions → New repository secret**

Crea:

```text
HANDBALL_APP_URL
```

Valore:

```text
https://TUO-SITO.onrender.com
```

Poi crea:

```text
HANDBALL_SYNC_TOKEN
```

con il valore copiato da Render.

### C. Test manuale

Vai su:

**GitHub → Actions → Sync FIGH data → Run workflow**

Il job deve terminare in verde.

## Come funziona l'orario

Il workflow contiene due finestre UTC per ciascun orario locale, così continua a funzionare con ora solare/legale italiana. La webapp esegue realmente il sync soltanto quando l'ora locale `Europe/Rome` è 07 oppure 23; la chiamata ridondante viene ignorata.

Il controllo è quotidiano, non soltanto mercoledì/sabato/domenica: questo permette di intercettare anticipi, posticipi e recuperi in giorni anomali. Il report ChatGPT delle 23 resta invece il controllo indipendente richiesto.

## Database e sicurezza

- `DATABASE_URL` resta solo nelle variabili segrete di Render.
- `SYNC_TOKEN` protegge l'endpoint usato dall'automazione GitHub.
- Il database non vive sul filesystem di Render, quindi un riavvio o uno sleep della webapp non cancella lo storico.
- Puoi sempre scaricare un backup da **Esporta backup** nella dashboard.

## Se qualcosa non funziona

I tre controlli più utili sono:

1. `/healthz` deve rispondere con `database: PostgreSQL`;
2. nei log Render non deve comparire `DATABASE_URL non configurato`;
3. GitHub Actions deve avere entrambi i secrets `HANDBALL_APP_URL` e `HANDBALL_SYNC_TOKEN`.
