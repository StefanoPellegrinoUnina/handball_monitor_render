from db import init_db, upsert_match, replace_report_details

init_db()
match={
  "competition":"A Gold M","season":"2026/2027","round_no":2,"match_no":10,
  "played_at":"2026-09-19T16:00","venue_city":"CHIARAVALLE","venue_name":"PALASPORT - VIA FIRENZE .",
  "home_team":"PUBLIESSE CHIARAVALLE","away_team":"TEAMNETWORK ALBATRO SIRACUSA",
  "home_goals":25,"away_goals":27,"home_ht":9,"away_ht":14,"status":"played",
  "source_url":"https://www.federhandball.it/campionati-nazionali/serie-a-gold/calendario-e-risultati/",
  "report_url":"https://campionati.mps-service.it/camp3/stampa_referto_pubblico/17379","report_id":"17379","checksum":"demo"
}
mid=upsert_match(match)
players_a=[('1','MAISTRELLO ALESSANDRO',0),('6','D`BENEDETTO PIERO',6),('7','GEGEA GHEORGHITA ANDREI',0),('8','BABBINI MARCO',0),('10','SANTINELLI OMAR',0),('13','PARMEGGIANI ALESSANDRO',3),('18','DI DOMENICO MARTIN',1),('20','CAPATINA MARIO ANDREI',0),('22','SAMPAOLO VALERIO',0),('33','BALLABIO FRANCESCO',0),('35','SANCEZ ARAUJO RENATO ALEXANDRE',4),('36','ALTOMONTE FRANCESCO ANGELO',4),('48','MIRI MOHAMMED',2),('62','BELARDINELLI ALEX',3),('69','AQUILI GABRIELE',0),('84','BETAIEB MOHAMED HACHMI',2)]
players_b=[('1','RIAHI SALAH',0),('2','PIVATO DAVIDE',1),('3','KUCSERA MIKULAS',7),('4','MARINO VITO CLAUDIO',1),('5','LORENTZEN JAKOB FALK',1),('7','ANGIOLINI FILIPPO',4),('8','ZUNGRI JUAN IGNACIO',1),('10','CORREIA BAPTISTA JOSE MIGUEL',3),('18','ARCIERI STEFANO',0),('21','MAZZONE ANDREA',1),('22','COUTINHO BRAGA FELIPE CESAR',1),('24','GUGGINO CRISTIAN',7),('39','HERMONES SILVA PEDRO HENRIQUE',0)]
participants=[]
for no,n,g in players_a: participants.append({"side":"A","team":match['home_team'],"person_type":"player","shirt_no":no,"name":n,"goals":g})
for no,n,g in players_b: participants.append({"side":"B","team":match['away_team'],"person_type":"player","shirt_no":no,"name":n,"goals":g})
for side,team,off in [('A',match['home_team'],[('UFF.A','POLVERINI CORRADO'),('UFF.B','GUIDOTTI ANDREA'),('UFF.C','HAMMOUDA FEHMI'),('UFF.D','GIAMBARTOLOMEI CRISTIANO')]),('B',match['away_team'],[('UFF.A','DI STEFANO GABRIELE'),('UFF.B','GARRALDA LARUMBE MATEO JESUS'),('UFF.C','BUFARDECI ANGELO')])]:
  for role,n in off: participants.append({"side":side,"team":team,"person_type":"team_official","official_role":role,"name":n,"goals":0})
sanctions=[
 {"side":"B","team":match['away_team'],"person_type":"player","shirt_no":"3","person_name":"KUCSERA MIKULAS","sanction_type":"2min","minute":"35:02","ordinal":1,"source_column":"4"},
 {"side":"B","team":match['away_team'],"person_type":"player","shirt_no":"5","person_name":"LORENTZEN JAKOB FALK","sanction_type":"2min","minute":"48:02","ordinal":1,"source_column":"4"},
 {"side":"B","team":match['away_team'],"person_type":"team_official","official_role":"UFF.B","person_name":"GARRALDA LARUMBE MATEO JESUS","sanction_type":"warning","minute":"48:35","source_column":"3"},
 {"side":"B","team":match['away_team'],"person_type":"team_official","official_role":"UFF.B","person_name":"GARRALDA LARUMBE MATEO JESUS","sanction_type":"2min","minute":"49:03","ordinal":1,"source_column":"4"},
]
assignments=[{"role":"Arbitro 1","person_name":"Simone F."},{"role":"Arbitro 2","person_name":"Monitillo P."},{"role":"Commissario 1","person_name":"Piffanelli C."}]
replace_report_details(mid,participants,sanctions,assignments)
print('seeded',mid)
