# yt-chapters omalla palvelimella

Tämä repo sisältää koodin ja opastuksen botin virittämiseen, joka hoitaa YouTube-livelähetysten kuvaukset ja aikaleimat.

Tämä ohje opastaa asennuksen omalle Linux-palvelimelle (VPS), jossa systemd-ajastin käynnistää botin tunnin välein. Botti voidaan ajaa myös GitHub Actionsissa ilman omaa palvelinta; siihen on [erillinen ohje](README.md).

Tavoitteena on hyvin spesifin tarpeen täyttäminen: pitkien livelähetysten, esimerkiksi opetusluentojen, seminaarien ja vastaavien lähetysten katseleminen on aikaleimojen kanssa huomattavasti helpompaa. Aikaleimat auttavat siirtymään livelähetyksessä kiinnostavaan kohtaan ja ymmärtämään sen sisältöä paremmin - ja myöskin skippaamaan turhat mainokset. YouTube ei tee aikaleimoja automaattisesti, mutta tekee näihin kuitenkin automaattisen tekstityksen.

Tämä botti hakee tuon tekstityksen ja nykyisen kuvauksen yksityiseen datarepoosi. Sinä muokkaat kuvausta lisäämällä aikaleimat mieleiselläsi tavalla, esimerkiksi kielimallin avulla (repo sisältää valmiiksi CLAUDE.md:n, mutta voit lisätä ohjeet haluamallesi kielimallille). Kun pusket päivitetyn kuvauksen datarepoon, botti julkaisee kuvauksen YouTubeen.

Huomautus: Botti vie vain **livelähetysten** kuvaukset, **ei tavallisten videoiden**. Tavallisen videon voi lisätä käsin, ks. [Komennot](#komennot). Myöskään tekstityksen muokkaus ei ole mahdollista: botti tuo YouTuben tekemän tekstityksen sellaisenaan. Jos haluat muokata tekstitystä, tee se YouTube Studiossa.

Alla kuvataan [repojen rakenne](#repojen-rakenne), [käyttö](#käyttö) ja [asennus](#asennus). Asennukseen tarvitset:

 * Linux-palvelimen (Debian tai Ubuntu), jolle on ssh-yhteys ja sudo-oikeus
 * GitHub-tilin, jolla on oikeus luoda yksityisiä repoja
 * Google-tilin, jolla on oikeus hallita YouTube-kanavaa
 * (Valinnainen) Claude API -avain, jolloin saat valmiin ehdotuksen kuvauksesta
 * (Valinnainen) Sähköpostitili, josta botti voi lähettää ilmoituksia sinulle

## Repojen rakenne

Repoja on kaksi:

- **Koodirepo** `yt-chapters` (julkinen, tämä repo tai sen forkki): botin koodi, systemd-tiedostot ja tämä ohje. Palvelin vain lukee sitä.
- **Datarepo** `yt-chapters-data` (yksityinen, luot tämän itse): videoiden kuvaukset ja tekstitykset. Botti kirjoittaa sinne, ja sinä muokkaat sitä.

Jako on tehty tietoturvan vuoksi. Datarepo ei sisällä YouTube-tunnuksia, joten sinne kirjoittava henkilö tai työkalu ei pääse niihin käsiksi. Tunnukset ja botin tila pysyvät palvelimella.

Alla olevissa ohjeissa `OMISTAJA` tarkoittaa GitHub-käyttäjätunnustasi ja `PALVELIN` palvelimen ssh-osoitetta. Korvaa ne omillasi.

## Käyttö

Kun olet asentanut botin, sen käyttö tapahtuu seuraavasti:

1. (Sinä:) Pidä livelähetys normaaliin tapaan.
2. (YouTube:) Livelähetyksen päättyessä YouTube tekee sille tekstityksen. Tämä voi kestää 24 tuntia tai kauemmin.
3. (Botti:) Botti tarkistaa uudet livelähetykset tunnin välein.
4. (Botti:) Botti lataa YouTubesta tekstityksen ja nykyisen kuvauksen ja pushaa ne yksityiseen datarepoon.
5. (Valinnainen:) Botti lähettää sähköpostin sinulle, kun push on valmis.
6. (Sinä:) Ota `git pull` datareposta ja avaa videon kansio, esimerkiksi `videos/2024-06-01-abc123/`.
7. (Sinä:) Muokkaa kuvausta (`description.txt`), esimerkiksi lisää aikaleimat.
8. (Sinä:) Tee `git commit -am "Aikaleimat"` ja `git push` datarepoon.
9. (Botti:) Botti tarkistaa kuvauksen ja julkaisee sen YouTubeen seuraavalla ajolla, joka on tunnin välein.
10. (Valinnainen:) Jos haluat julkaista heti, aja palvelimella `$Y run` (ks. [Komennot](#komennot)).

## Mitä videokansio sisältää

Datarepo sisältää videokohtaiset kansiot, joissa on kuvaus ja tekstitys. Botti luo kansion automaattisesti. Kansion nimi on muotoa `videos/<pvm>-<videoID>/`. `<pvm>` on lähetyksen päättymispäivä, ja käsin lisätyllä (ks. [Komennot](#komennot)) videolla lisäyspäivä. Päivä on UTC-ajassa, joten Suomen iltana päättynyt lähetys voi saada edellisen päivän päivämäärän.

Kansio sisältää seuraavat tiedostot. Sinä muokkaat vain tiedostoa `description.txt`. Botti muokkaa muita tiedostoja.

| Tiedosto                     | Kuka muokkaa | Sisältö                                                                                                                                |
| ---------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `description.txt`            | **sinä**     | Videon kuvaus. Pushattu muutos julkaistaan. Aluksi tiedostossa on YouTuben nykyinen kuvaus.                                            |
| `transcript.txt`             | botti        | Tekstitys muodossa `[aikaleima] teksti`, 15 s ikkunoina                                                                                |
| `subtitles.srt`, `meta.json` | botti        | Alkuperäinen tekstitys sekä otsikko, kesto ja linkit                                                                                   |
| `ehdotus.txt`                | botti        | Claude API:n ehdotus koko kuvaukseksi, jos `[llm] enabled = true`. Tätä ei julkaista: kopioi siitä `description.txt`:hen, mitä haluat. |
| `VIRHEET.txt`                | botti        | Syy, miksi julkaisu estettiin. Korjaa `description.txt` ja pushaa. Tiedosto poistuu, kun korjattu versio julkaistaan.                  |
| `description.youtube.txt`    | botti        | Ristiriita: kuvausta muokattiin YouTube Studiossa. Yhdistä muutokset `description.txt`:hen, poista tämä tiedosto ja pushaa.            |

### Julkaisun säännöt

- Julkaisu käynnistyy, kun `description.txt` eroaa siitä, mitä botti viimeksi kirjoitti tai julkaisi. Pelkkä rivinvaihtojen tyyppi tai rivien lopun välilyönnit eivät riitä. Kansio säilyy repossa, joten kuvausta voi muokata myöhemminkin.
- Botti muuttaa YouTubessa vain kuvausta. Otsikko ja tagit säilyvät.
- Kuvaus saa olla enintään 5000 merkkiä, eikä siinä saa olla merkkejä `<` tai `>`.
- Aikaleimoiksi tulkitaan kuvauksen pisin yhtenäinen rivilohko muotoa `MM:SS Otsikko` tai `H:MM:SS Otsikko`. Ensimmäisen aikaleiman pitää olla 00:00, ja aikaleimoja pitää olla vähintään kolme nousevassa järjestyksessä vähintään 10 s välein. Viimeisen aikaleiman pitää olla vähintään 10 s ennen videon loppua.
- Muokkaa kuvausta vain repossa. Studiossa tehty muutos ei tule repoon, ja seuraava push aiheuttaa ristiriidan.

### Uudet livelähetykset

Botti ottaa mukaan vain ne livelähetykset, jotka ovat päättyneet asennuksessa valitun ajankohdan jälkeen, jotta kanavan vanhat lähetykset eivät tule jonoon. Ajankohta asetetaan `config.toml`:n kohtaan `start_after` (ks. [asennuksen kohta 4](#4-ohjelma-ja-asetukset)). Botti tarkistaa tekstityksen tunnin välein, joten video tulee repoon noin tunnin kuluessa siitä, kun YouTuben tekstitys on valmis. Jos tekstitystä ei ole 72 tunnin kuluttua, botti luovuttaa.

Muun videon, esimerkiksi vanhan tai tavallisen videon, voi lisätä käsin komennolla `$Y add VIDEO_ID` (ks. [Komennot](#komennot)).

### Ohjeet kielimallille

Botti luo datarepoon myös `README.md`:n ja `CLAUDE.md`:n. Niiden ansiosta voit avata datarepon Claude Codessa ja pyytää esimerkiksi "tee aikaleimat uusimmalle videolle", ilman API-kuluja. Claude committaa muutoksen mutta pushaa vain pyydettäessä, koska push julkaisee kuvauksen. Voit luonnollisesti tehdä itse oman ohjeen kielimallille ja poistaa CLAUDE.md:n. Botti ei luo poistettua tiedostoa uudelleen.

## Asennus

Komennot ajetaan palvelimella omana käyttäjänäsi, paitsi rivit, joiden lopussa lukee `# omalta koneelta`. *Oma kone* on kone, jonka selainta käytät (esim. läppäri), ei palvelin.

Alla oletetaan, että koodirepo kloonataan palvelimelle kansioon `~/yt-chapters`. Botti asennetaan hakemistoon `/opt/yt-chapters/`, sen asetukset hakemistoon `/etc/yt-chapters/` ja tila hakemistoon `/var/lib/yt-chapters/`.

### 1. Google Cloud

1. Mene osoitteeseen <https://console.cloud.google.com/>. Luo projekti ja ota käyttöön **YouTube Data API v3**.
2. Määritä OAuth consent screen: tyyppi *External*, lisää oma tilisi ja vaihda tilaksi *In production*. *Testing*-tilassa refresh token vanhenee 7 päivässä. Jos tilaa ei voi vaihtaa, katso [Vianetsintä](#vianetsintä).
3. Luo Credentials → OAuth client ID, tyyppi **Desktop app**, ja lataa `client_secret.json`. Tiedosto kopioidaan kohdassa 2 palvelimelle, eikä sitä viedä GitHubiin.

### 2. Koodi palvelimelle

Koodirepo on julkinen, joten se kloonataan HTTPS:llä eikä palvelin tarvitse siihen avainta. Jos forkkasit repon, käytä forkin osoitetta.

```bash
sudo apt install git openssh-client python3 python3-venv
git clone https://github.com/OMISTAJA/yt-chapters.git ~/yt-chapters
```

Kopioi kohdassa 1 ladattu `client_secret.json` palvelimelle:

```bash
scp ~/Downloads/client_secret_*.json PALVELIN:yt-chapters/client_secret.json   # omalta koneelta
```

### 3. Botin käyttäjä ja datarepo

Botti ajetaan omana järjestelmäkäyttäjänään `ytchapters`, jolla ei ole kotihakemistoa eikä kirjautumisoikeutta. Sen tila pidetään hakemistossa `/var/lib/yt-chapters/`, jonne luodaan myös avain, jolla botti kirjoittaa datarepoon:

```bash
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin ytchapters
sudo install -d -o ytchapters -g ytchapters -m 700 /var/lib/yt-chapters /var/lib/yt-chapters/ssh
sudo -u ytchapters ssh-keygen -t ed25519 -N "" -C yt-chapters -f /var/lib/yt-chapters/ssh/id_ed25519
sudo cat /var/lib/yt-chapters/ssh/id_ed25519.pub
```

Luo GitHubiin uusi **yksityinen** repo (esim. `OMISTAJA/yt-chapters-data`). Jätä se täysin tyhjäksi, eli älä lisää README-, .gitignore- tai lisenssitiedostoa. Botti luo ensimmäisellä ajolla `main`-haaran sekä `README.md`:n ja `CLAUDE.md`:n. Valmiiksi olemassa olevaa README:tä se ei korvaa, eikä se luo kumpaakaan uudelleen, jos poistat sen.

Lisää yllä tulostettu julkinen avain datarepon kohtaan *Settings* → *Deploy keys* → *Add deploy key*. Anna *Title*-kenttään esimerkiksi `yt-chapters`, liitä avain *Key*-kenttään ja valitse *Allow write access*. Nimi on tunniste, jolla avaimen löytää listasta myöhemmin. Ota talteen myös repon SSH-osoite (`git@github.com:...`), sillä sitä tarvitaan kohdassa 4.

### 4. Ohjelma ja asetukset

Komennot asentavat botin hakemistoon `/opt/yt-chapters/` omaan Python-ympäristöönsä (venv) kirjastoineen. Sitten ne siirtävät asetustiedoston ja `client_secret.json`:n hakemistoon `/etc/yt-chapters/` niin, että vain root ja botin käyttäjä voivat lukea niitä, ja avaavat `config.toml`:n muokattavaksi.

```bash
cd ~/yt-chapters
sudo install -d /opt/yt-chapters /etc/yt-chapters
sudo cp yt_chapters.py /opt/yt-chapters/
sudo python3 -m venv /opt/yt-chapters/venv
sudo /opt/yt-chapters/venv/bin/pip install google-api-python-client google-auth-oauthlib
# vain jos [llm] enabled = true:
sudo /opt/yt-chapters/venv/bin/pip install anthropic

sudo cp config.example.toml /etc/yt-chapters/config.toml
sudo mv client_secret.json /etc/yt-chapters/
sudo chown root:ytchapters /etc/yt-chapters/*
sudo chmod 640 /etc/yt-chapters/*
sudoedit /etc/yt-chapters/config.toml
```

Komento on `python3`, ei `python`. Virtuaaliympäristö tarvitaan, koska uudet Debian-pohjaiset jakelut eivät salli pip-asennuksia suoraan järjestelmän Pythoniin.

Muuta tiedostosta ainakin nämä:

- `[youtube]`-osio: lisää tiedoston loppuun. Sitä ei ole esimerkissä, koska GitHub Actions -asennus ei tarvitse sitä.

```toml
[youtube]
client_secret = "/etc/yt-chapters/client_secret.json"
```

- `repo_url`: datarepon SSH-osoite (kohta 3).
- `start_after`: vain tämän (muodossa `YYYY-MM-DDTHH:MM:SSZ`, UTC-aika) jälkeen päättyneet lähetykset otetaan mukaan. Aseta asennuspäivä, ettei koko historia tule jonoon.
- `author_email`: esim. `yt-chapters@localhost`. Tämä vaikuttaa vain datarepon committeihin.
- `context` (`[general]`-osiossa): kerro kielimallille, millaisista videoista on kyse. Tarvitaan vain, jos `[llm]` on käytössä.
- `[email]` (valinnainen): ilmoitukset uusista videoista, virheistä ja julkaisuista, ks. [Sähköposti-ilmoitukset](#sähköposti-ilmoitukset). Jos et halua ilmoituksia, poista osio.
- `[llm]` (valinnainen): Claude API kirjoittaa `ehdotus.txt`:n. Aseta `enabled = true` ja laita API-avain kenttään `api_key`. Ympäristömuuttuja `ANTHROPIC_API_KEY` ei toimi, koska systemd-palvelu ei näe sitä.

Muut rivit jätetään ennalleen: `state_dir` ja `ssh_key` vastaavat polkuja, joita systemd-palvelu ja kohta 3 käyttävät.

#### Sähköposti-ilmoitukset

Botti lähettää ilmoitukset SMTP:llä. Helpoin tapa on luoda botille oma Gmail-tili. Organisaatioiden Microsoft 365 -tilit eivät yleensä käy, koska ne eivät salli SMTP-kirjautumista salasanalla.

1. Luo botille Gmail-tili ja kytke siihen 2-vaiheinen vahvistus. Ilman sitä sovellussalasanoja ei voi luoda.
2. Luo sovellussalasana osoitteessa https://myaccount.google.com/apppasswords (nimeksi esim. `yt-chapters`). Google näyttää sen vain kerran. Tilin tavallinen salasana ei kelpaa.
3. Täytä `config.toml`:n `[email]`-osio:

```toml
[email]
enabled = true
from_address = "botti@gmail.com"      # botin Gmail-tili
to_address = "sinä@example.fi"        # minne ilmoitukset tulevat
username = "botti@gmail.com"          # sama kuin from_address
password = "..."                      # sovellussalasana ilman välilyöntejä
smtp_host = "smtp.gmail.com"
smtp_port = 465
smtp_starttls = false
```

Kokeile lähetystä:

```bash
sudo -u ytchapters /opt/yt-chapters/venv/bin/python -c "
import sys, tomllib; sys.path.insert(0, '/opt/yt-chapters'); import yt_chapters as y
y.notify(tomllib.load(open('/etc/yt-chapters/config.toml', 'rb')), 'yt-chapters: testi', 'Sähköposti toimii.')"
```

Jos komento ei tulosta mitään, viesti lähti. Jos se tulostaa virheen, katso [Vianetsintä](#vianetsintä).

### 5. YouTube-kirjautuminen

Kirjautuminen tehdään palvelimella botin käyttäjänä, jolloin token tallentuu suoraan botin tilahakemistoon. Googlen kirjautumissivu ohjaa selaimen takaisin palvelimen porttiin 8765, joten avaa omalta koneelta ssh-yhteys, joka välittää tuon portin, ja aja samassa istunnossa `auth`:

```bash
ssh -L 8765:localhost:8765 PALVELIN        # omalta koneelta
sudo -u ytchapters /opt/yt-chapters/venv/bin/python /opt/yt-chapters/yt_chapters.py \
  --config /etc/yt-chapters/config.toml auth
```

Avaa tulostunut URL oman koneen selaimessa ja kirjaudu kanavan omistavalla tilillä. Jos Google varoittaa vahvistamattomasta sovelluksesta, jatka kohdasta *Advanced*. Kirjautuminen on valmis, kun komento tulostaa `Token tallennettu`.

Tee tämä uudelleen aina, kun botti ilmoittaa kirjautumisen vanhentuneen.

### 6. Kokeilu ja ajastus

Kokeile ensin käsin jollakin omalla videolla. Videolla pitää olla tekstitys, ja se voi olla vanhakin.

```bash
Y="sudo -u ytchapters /opt/yt-chapters/venv/bin/python /opt/yt-chapters/yt_chapters.py --config /etc/yt-chapters/config.toml"
$Y add VIDEO_ID      # lisää video jonoon
$Y run               # botti vie videon datarepoon
$Y status            # tilan pitäisi olla in_repo
```

Tarkista, että datarepon `main`-haaraan tuli videon kansio. Jos sähköposti-ilmoitukset ovat käytössä, sinulle tulee viesti "Uusi video repossa".

Ota sitten ajastus käyttöön:

```bash
sudo cp ~/yt-chapters/yt-chapters.service ~/yt-chapters/yt-chapters.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yt-chapters.timer
systemctl list-timers yt-chapters.timer   # seuraava ajo
```

Tästä eteenpäin botti ajetaan tunnin välein.

## Ylläpito

Botti pyörii palvelimella käyttäjänä `ytchapters`, ja systemd-ajastin `yt-chapters.timer` käynnistää sen tunnin välein. Palvelu `yt-chapters.service` ajaa komennon `run` ja lopettaa.

### Missä mikäkin on

| Polku palvelimella      | Sisältö                                                                                                                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `~/yt-chapters/`        | Koodirepon klooni, josta päivitykset asennetaan                                                                                                                                            |
| `/opt/yt-chapters/`     | Asennettu `yt_chapters.py` ja Python-venv                                                                                                                                                  |
| `/etc/yt-chapters/`     | `config.toml` ja `client_secret.json`                                                                                                                                                      |
| `/var/lib/yt-chapters/` | Botin tila: `token.json` (YouTube-kirjautuminen), `state.db` (videoiden tila), `repo/` (datarepon klooni) ja `ssh/` (datarepon deploy key). Älä poista hakemistoa: tyhjästä tilasta aloittava botti kirjoittaisi julkaisemattomien kuvausten päälle. |
| `/etc/systemd/system/`  | `yt-chapters.service` ja `yt-chapters.timer` (ajo tunnin välein)                                                                                                                           |
| systemd-journal         | Botin loki, ks. [Komennot](#komennot)                                                                                                                                                      |

### Komennot

Botti käynnistetään käsin palvelimella. Komennot ajetaan botin käyttäjänä ja botin omalla Python-ympäristöllä, joten määrittele ensin lyhenne `$Y`:

```bash
# lyhenne, jota $Y-komennot käyttävät (voimassa vain tässä shell-istunnossa)
Y="sudo -u ytchapters /opt/yt-chapters/venv/bin/python /opt/yt-chapters/yt_chapters.py --config /etc/yt-chapters/config.toml"
$Y status                                 # seuratut videot ja niiden tila
$Y add VIDEO_ID                           # lisää video tai hae sen tekstitys uudelleen
$Y run                                    # aja kierros heti ajastusta odottamatta
journalctl -u yt-chapters -n 50           # loki (-f seuraa jatkuvasti)
systemctl list-timers yt-chapters.timer   # seuraava ajo
```

- **Aja heti** ajastusta odottamatta: `$Y run` tekee saman kuin ajastettu ajo. Se julkaisee pushatut kuvaukset ja hakee uudet lähetykset ja tekstitykset.
- **Lisää video** tai hae sen tekstitys uudelleen: `$Y add VIDEO_ID`. Video käsitellään seuraavalla ajolla, tai heti komennolla `$Y run`. Jos video on jo repossa, botti hakee tekstityksen uudelleen mutta ei kirjoita julkaisemattomien muokkauksien päälle.

`VIDEO_ID` on videon tunniste osoitteessa `https://youtu.be/VIDEO_ID`.

`$Y status` näyttää kunkin videon tilan:

- `waiting`: odottaa tekstitystä.
- `in_repo`: video on repossa, ja `description.txt`:n muutokset julkaistaan.
- `failed`: botti luovutti. Syy näkyy rivin lopussa.

Jos julkaisu estyy, botti kirjoittaa syyn videon kansioon ja lähettää sähköpostin, jos ilmoitukset ovat käytössä. Jos koko ajo epäonnistuu, syy löytyy lokista (`journalctl -u yt-chapters`).

### Päivitys

- **Koodi:** hae uusi versio ja kopioi se paikoilleen. Uusi versio on käytössä seuraavalla ajolla, eikä mitään tarvitse käynnistää uudelleen.

```bash
cd ~/yt-chapters && git pull
sudo cp yt_chapters.py /opt/yt-chapters/
```

- **systemd-tiedostot:** jos `yt-chapters.service` tai `yt-chapters.timer` muuttui, kopioi ne kuten asennuksen kohdassa 6 ja aja `sudo systemctl daemon-reload && sudo systemctl restart yt-chapters.timer`.
- **Asetukset:** muokkaa tiedostoa `/etc/yt-chapters/config.toml` (`sudoedit`). Jos `config.example.toml`:ään tuli uusia asetuksia, lisää ne käsin.

## Vianetsintä

Botin loki on systemd-journalissa: `journalctl -u yt-chapters -n 50`.

| Oire                                                                                                                    | Mitä tehdä                                                                                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Kuvaus ei päivity pushin jälkeen                                                                                        | Aja datarepossa `git pull` ja katso, onko videon kansiossa `VIRHEET.txt` tai `description.youtube.txt`. Jos kumpaakaan ei ole, katso loki.                                                                          |
| Push datarepoon hylätään                                                                                                | Botti pushasi välissä. Aja `git pull --rebase` ja pushaa uudelleen.                                                                                                                                                |
| Lokissa `Permission denied (publickey)`                                                                                 | `/var/lib/yt-chapters/ssh/id_ed25519` ei vastaa datarepon deploy keytä, tai Allow write access puuttuu. Luo uusi avainpari kuten kohdassa 3.                                                                       |
| Lokissa `TOMLDecodeError` tai `KeyError`                                                                                | `config.toml` on virheellinen tai siitä puuttuu kenttä. Vertaa `/etc/yt-chapters/config.toml`:ää `config.example.toml`:ään.                                                                                        |
| Ajastetut ajot eivät käynnisty                                                                                          | Tarkista `systemctl list-timers yt-chapters.timer`. Jos ajastinta ei ole listalla, aja `sudo systemctl enable --now yt-chapters.timer`. Palvelun oma virhe näkyy komennolla `systemctl status yt-chapters`.        |
| Uusi lähetys ei tule repoon                                                                                             | Katso `$Y status`. Tila `waiting` tarkoittaa, että tekstitys ei ole vielä valmis. Jos videota ei ole listalla, se luultavasti päättyi ennen `start_after`-aikaa: lisää se komennolla `$Y add VIDEO_ID`.            |
| Videon tila on `failed`                                                                                                 | Tekstitystä ei löytynyt 72 tunnissa, tai vienti repoon epäonnistui kolmesti. Korjaa syy ja aja `$Y add VIDEO_ID`.                                                                                                  |
| Sähköposti "YouTube-kirjautuminen vanhentunut" tai lokissa `RefreshError`                                               | Kirjaudu uudelleen: [asennuksen kohta 5](#5-youtube-kirjautuminen).                                                                                                                                                |
| Sähköposteja ei tule                                                                                                    | Aja [testikomento](#sähköposti-ilmoitukset). Jos se tulostaa virheen, katso seuraavat rivit. Tarkista myös, että `[email]`-osiossa on `enabled = true`.                                                            |
| Testikomento tulostaa `534 5.7.9 Application-specific password required`                                                | `password`-kentässä on tilin tavallinen salasana. Vaihda tilalle sovellussalasana.                                                                                                                                 |
| Testikomento tulostaa `535 Username and Password not accepted`                                                          | Sovellussalasana on väärin, tai se on poistettu. Luo uusi sovellussalasana ja laita se `password`-kenttään.                                                                                                        |
| Testikomento päättyy aikakatkaisuun                                                                                     | Palvelin ei saa yhteyttä porttiin 465. Kokeile asetuksia `smtp_port = 587` ja `smtp_starttls = true`.                                                                                                              |
| OAuth consent screenin tilaa ei voi vaihtaa Testingistä "In production" -tilaan ([asennuksen kohta 1](#1-google-cloud)) | Täytä ensin consent screenin tiedoista sovelluksen nimi (*App name*), kotisivun osoite (*Application home page*) ja tietosuojaselosteen osoite (*Application privacy policy link*).                                |
