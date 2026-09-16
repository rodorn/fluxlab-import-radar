# ImportRadar

Radar oplacalnosci importu aut z Niemiec i Holandii do Polski dla handlarzy i osob prywatnych.

Narzedzie CLI liczy pelny koszt sprowadzenia auta (cena, akcyza, transport, tlumaczenie,
rejestracja, badanie, bufor na usterki), porownuje z realistyczna cena sprzedazy w PL
i zwraca ranking marzy netto: "te auta z DE oplaca sie teraz sprowadzic, marza X".

Projekt FluxLab, [fluxlab.pl](https://fluxlab.pl).

## Co robi

- **`scan`** - buduje ranking marzy netto dla wielu ofert DE vs ceny sprzedazy PL. Output: tabela "Top aut do sprowadzenia" z linkami, cena DE, szac. cena PL, policzona marza netto. Raport Markdown, HTML i PDF.
- **`calc`** - liczy oplacalnosc jednego auta (wejscie: cena DE, cena PL, pojemnosc silnika, klasa).

Serce narzedzia to kalkulator kosztu importu (`import_radar/calculator.py`), pokryty testami.

### Jak liczona jest akcyza

- 3,1 proc. dla pojemnosci silnika do 2000 cm3 wlacznie,
- 18,6 proc. powyzej 2000 cm3,
- 0 proc. dla aut w pelni elektrycznych (BEV).

Podstawa akcyzy to wartosc auta (cena zakupu przeliczona na PLN). Nabycie uzywanego auta
wewnatrz UE nie rodzi cel ani VAT importowego, dlatego VAT domyslnie wynosi 0
(mozna go wlaczyc parametrem, gdy dotyczy transakcji).

## Uruchomienie

```bash
git clone https://github.com/rodorn/fluxlab-import-radar.git
cd fluxlab-import-radar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ranking na dolaczonych przykladowych danych (dziala od reki):
python -m import_radar.cli scan --top 10

# Zapis raportu do PDF (wymaga google-chrome-stable):
python -m import_radar.cli scan --pdf out/raport.pdf --md out/raport.md

# Oplacalnosc jednego auta:
python -m import_radar.cli calc --price-eur 15900 --pl-price 86000 --cc 1995 --class premium_mid

# Wlasne dane wejsciowe (JSON lub CSV z ofertami DE + JSON z cenami PL):
python -m import_radar.cli scan --de moje_de.json --pl moje_pl.json --eur 4.32

# Proba pobrania na zywo z autoscout24 (fallback do pliku, gdy zablokowane):
python -m import_radar.cli scan --live volkswagen golf
```

## Zrodla danych

- **Fallback (domyslnie)**: pliki JSON/CSV z ofertami DE oraz JSON z porownawczymi cenami PL.
  W repo jest dolaczony realistyczny przykladowy dataset (`data/sample_*.json`, oznaczony PRZYKLAD),
  dzieki czemu narzedzie liczy pelny ranking od razu po instalacji.
- **Live scrape**: warstwa `scraper.py` probuje pobrac listing z autoscout24 (naglowki przegladarki,
  throttling). Portale DE agresywnie blokuja scraping (Cloudflare, render po stronie JS), wiec przy
  blokadzie narzedzie automatycznie przechodzi na dane z pliku. Sposob docelowy zasilania danymi:
  eksport ofert do JSON/CSV oraz mediany cen PL z Otomoto.

Format wejscia (JSON ofert DE) i cen PL: patrz `data/sample_de_offers.json` i `data/sample_pl_prices.json`.

## Przykladowy raport

`out/sample_import_radar.pdf` (wygenerowany na przykladowych danych, demo).

## Testy

```bash
pytest -q
```

Testy pokrywaja kalkulator importu (akcyza wg pojemnosci, VAT, oplaty, bufor, marza)
oraz parser ofert. CI (GitHub Actions) uruchamia je na Pythonie 3.10 i 3.12.

## Cennik uslugi

| Pakiet              | Cena              | Zakres                                                                                |
| ------------------- | ----------------- | ------------------------------------------------------------------------------------- |
| Analiza 1 auta      | 100 - 200 zl      | Pelna kalkulacja oplacalnosci konkretnej oferty DE, z rozbiciem kosztow i marza netto |
| "Znajdz pod budzet" | 200 - 300 zl      | Ranking najbardziej oplacalnych aut do sprowadzenia w zadanym budzecie i segmencie    |
| Subskrypcja         | 149 - 299 zl / mc | Cykliczny raport okazji importowych w wybranych modelach                              |
| Wersja komis        | 400 - 800 zl / mc | Rozszerzony radar dla handlarzy, wieksze wolumeny i priorytet                         |

## Zastrzezenie o danych

Raport ma charakter pogladowy. Marza netto to szacunek, nie gwarancja. Realne koszty (transport,
usterki, czas sprzedazy) oraz ceny rynkowe moga sie roznic. Dolaczony dataset jest przykladowy
i sluzy do prezentacji dzialania narzedzia, nie jest odczytem rynku live. Przed zakupem zawsze
weryfikuj VIN, historie i stan techniczny auta oraz aktualne stawki podatkowe.

Sekrety (tokeny, klucze) nie sa przechowywane w repozytorium.
