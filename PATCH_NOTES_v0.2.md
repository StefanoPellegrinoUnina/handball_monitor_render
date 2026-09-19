# Handball Monitor Italia — patch v0.2

Correzioni principali:

- parser dei referti: ignora le tabelle laterali (risultato, timeout, 7m, designazioni) come possibili rose;
- contesto A/B azzerato per ogni tabella PDF;
- filtro anti-righe numeriche e deduplicazione difensiva dei partecipanti;
- gestione separata per ufficiali di squadra: ammonizione, singolo 2', Sq., San Sq.;
- acquisizione 7m tiri/reti e memorizzazione come tentativi/realizzati;
- statistiche cumulative 7m per squadra;
- DQ dirette e DQ derivanti da 3x2' separate e totalizzate;
- dettaglio gara con rose, reti e minuti delle sanzioni;
- vecchie anomalie `report_parse` vengono marcate risolte quando lo stesso referto viene importato con successo;
- migrazione automatica e non distruttiva del database Neon esistente.

Dopo il deploy, premere **Aggiorna FIGH** una volta per riprocessare tutti i referti già scoperti.
