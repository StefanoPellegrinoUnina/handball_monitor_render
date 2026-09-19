# Handball Monitor Italia — versione gratuita

Dashboard stagionale per Serie A Gold maschile e Serie A1 femminile 2026/27.

Questa variante è pensata per funzionare senza disco persistente a pagamento:

- **Render Free** esegue la webapp FastAPI.
- **Neon Postgres Free** conserva lo storico in modo indipendente dal filesystem di Render.
- **GitHub Actions** sveglia la webapp e lancia le sincronizzazioni programmate.
- La webapp legge i calendari e i referti ufficiali FIGH/MPS e aggiorna il database.

## Dati registrati

- gare, giornata, numero gara, data/ora, sede, risultato e parziale;
- giocatori, reti e sanzioni;
- esclusioni da 2' con minuto e ordinale;
- squalifiche dirette e squalifica derivata dalla terza esclusione, tenute separate;
- ufficiali A/B/C/D e relative sanzioni con minuto;
- arbitro 1, arbitro 2, commissario/delegato 1 e 2;
- statistiche cumulative per squadra e giocatore;
- storico coppie arbitrali e delegati;
- registro anomalie e problemi di parsing;
- backup JSON completo.

## Avvio locale

Senza `DATABASE_URL` usa SQLite locale, utile per sviluppo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py
uvicorn app:app --reload
```

Per produzione su Render, `DATABASE_URL` deve essere configurato e deve puntare a PostgreSQL.

## Deploy

Segui `DEPLOY_FREE.md`.
