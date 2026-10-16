# 15.10.2026 – Tailscale-Hostnamen sicher zulassen

Der Geräte-Kurzname wurde bisher abgewiesen, weil die Host-Prüfung nur eingetragene
exakte Hostnamen und IP-Adressen kannte. `ERLAUBTE_HOSTS` bleibt standardmäßig leer
und akzeptiert jetzt zusätzlich ein ausdrücklich konfiguriertes Tailnet-Muster der
Form `*.<tailnet-domain>.ts.net`. Der kurze Gerätename muss weiterhin als exakter
Eintrag in derselben Komma-Liste stehen. Ein allgemeines `*.ts.net` und beliebige
Hostnamen bleiben gesperrt; es findet keine DNS-Auflösung statt. So gilt die Freigabe
nur für den eigenen, konfigurierten Tailnet-Namensraum und nicht für beliebige
öffentlich kontrollierte Namen.

Die Host-Prüfung akzeptiert Tailscale-IPv4 aus `100.64.0.0/10` ausdrücklich. Private
Heimnetz-Adressen und Loopback bleiben für die dokumentierte lokale Nutzung erlaubt;
öffentliche IP-Adressen außerhalb dieser Bereiche werden jetzt abgewiesen. Das ist
enger als die vorherige Freigabe aller IP-Literale. Die Herkunftsprüfung, Anmeldung
und API-Schlüssel-Prüfung bleiben unverändert: Ein zugelassener Hostname gewährt
keinen API-Zugriff und setzt keinem entfernten Client den Schlüssel ein.

Bei einer Host-Ablehnung (HTTP 400) nennt die `text/plain`-Antwort den abgelehnten
Host und die erlaubten Quellen. Derselbe Host wird begrenzt und ohne Steuerzeichen
im Server-Log vermerkt; Schlüssel oder andere Geheimnisse werden nicht ausgegeben.

## Eintrag auf dem Handy

In `backend/.env` die vorhandene Zeile `ERLAUBTE_HOSTS=` mit den eigenen Werten
befüllen. Schema mit Platzhaltern:

```dotenv
ERLAUBTE_HOSTS=<geraetename>,*.<tailnet-domain>.ts.net
```

`<geraetename>` durch den kurzen MagicDNS-Gerätenamen des Handys ersetzen und
`<tailnet-domain>` durch die konkrete Tailnet-Domain aus Tailscale. Die spitzen
Klammern sind Platzhalter und gehören nicht in den echten Wert. Der Wildcard gilt
nur für Namen unter genau dieser `.ts.net`-Domain; wer keine Tailnet-Untergeräte
freigeben möchte, lässt den zweiten Eintrag weg. Nach dem Ändern der `.env` den
Server auf dem Handy neu starten, damit die Konfiguration geladen wird.

## Offline-Prüfung

`backend/tests/test_sicherheit_herkunft.py` deckt den exakten Gerätenamen, die
konfigurierte Tailnet-Domain, fremde Namen und fremde Tailnets, leere Konfiguration,
Tailscale-IP-Grenzen, private Heimnetz-IP-Adressen sowie öffentliche IP-Ablehnungen
ab. Zusätzlich wird die hilfreiche Antwort samt Logeintrag geprüft.
