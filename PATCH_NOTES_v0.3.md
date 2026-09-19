# Patch v0.3 — parser strutturale referti FIGH

Questa versione corregge la lettura dei referti FIGH/MPS basandosi sulla struttura fisica delle tabelle PDF invece che sul testo lineare della pagina.

## Correzioni principali

- Arbitro 1 / Arbitro 2 / Commissario 1 / Commissario 2 vengono letti esclusivamente dal box laterale delle designazioni.
- Risultato, parziale del 1° tempo e 7m tiri/reti vengono letti dai rispettivi box laterali.
- Giocatori e ufficiali di squadra vengono riconosciuti esclusivamente nelle tabelle con intestazione `Cognome e Nome`.
- I giocatori sono identificati dal numero di maglia; gli ufficiali da `UFF.A`, `UFF.B`, `UFF.C`, `UFF.D`.
- Per i giocatori vengono conservati separatamente Amm., 1°/2°/3° 2', Sq. e San Sq.
- Per gli ufficiali viene gestito un solo slot 2', oltre ad Amm., Sq. e San Sq.
- Migliorata la correzione dei nomi con caratteri internazionali mal decodificati (es. Ø).
- La pagina di dettaglio gara separa esplicitamente `Giocatori` e `Ufficiali di squadra`.
- La pagina `Ufficiali di squadra` mostra tutte le presenze degli ufficiali, non soltanto quelli sanzionati.
- La pagina `Arbitri & delegati` mostra quattro colonne distinte: Arbitro 1, Arbitro 2, Commissario/Delegato 1, Commissario/Delegato 2.
- Migliorato il recupero della giornata dal calendario federale.

## Fixture verificata

Referto 17371 — MACAGI CINGOLI vs TRIESTE (12/09/2026):

- risultato 26–25;
- 1° tempo 13–11;
- 7m 4/3 e 4/4;
- Arbitro 1 Cardone C.;
- Arbitro 2 Cardone L.;
- Commissario 1 Carrino M.;
- UFF.A Trieste VINCI ADRIANO: ammonizione 41:06;
- somma reti giocatori A = 26;
- somma reti giocatori B = 25.

Dopo il deploy eseguire una volta `Aggiorna FIGH` per riprocessare e sostituire i dati errati già presenti nel database.
