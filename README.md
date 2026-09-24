# yt-chapters

Tämä repo sisältää koodin ja opastuksen botin virittämiseen, joka hoitaa YouTube-livelähetysten kuvaukset ja aikaleimat. 

Tämä ohje opastaa asennuksen GitHub Actionsiin. Botti voidaan ajaa myös omalla VPS:llä; siihen on [erillinen ohje](README-VPS.md).

Tavoitteena on hyvin spesifin tarpeen täyttäminen: pitkien livelähetysten, esimerkiksi opetusluentojen, seminaarien ja vastaavien lähetysten katseleminen on aikaleimojen kanssa huomattavasti helpompaa. Aikaleimat auttavat siirtymään livelähetyksessä kiinnostavaan kohtaan ja ymmärtämään sen sisältöä paremmin - ja myöskin skippaamaan turhat mainokset. YouTube ei tee aikaleimoja automaattisesti, mutta tekee näihin kuitenkin automaattisen tekstityksen.

Tämä botti hakee tuon tekstityksen ja nykyisen kuvauksen yksityiseen datarepoosi. Sinä muokkaat kuvausta lisäämällä aikaleimat mieleiselläsi tavalla, esimerkiksi kielimallin avulla (repo sisältää valmiiksi CLAUDE.md:n, mutta voit lisätä ohjeet haluamallesi kielimallille). Kun pusket päivitetyn kuvauksen datarepoon, botti julkaisee kuvauksen YouTubeen.

Huomautus: Botti vie vain **livelähetysten** kuvaukset, **ei tavallisten videoiden**. Tavallisen videon voi lisätä käsin, ks. [Komennot](#komennot). Myöskään tekstityksen muokkaus ei ole mahdollista: botti tuo YouTuben tekemän tekstityksen sellaisenaan. Jos haluat muokata tekstitystä, tee se YouTube Studiossa.

Alla kuvataan [repojen rakenne](#repojen-rakenne), [käyttö](#käyttö) ja [asennus](#asennus). Asennukseen tarvitset:

 * GitHub-tilin, jolla on oikeus luoda yksityisiä repoja
 * Google-tilin, jolla on oikeus hallita YouTube-kanavaa
 * Python 3, Git, ssh-keygen
 * (Valinnainen) Claude API -avain, jolloin saat valmiin ehdotuksen kuvauksesta
 * (Valinnainen) Sähköpostitili, josta botti voi lähettää ilmoituksia sinulle

## Repojen rakenne

Repoja on kaksi:

- **Koodirepo** `yt-chapters` (julkinen, forkkaat tämän): botin koodi, GitHub Actions -workflow ja YouTube-kirjautumisen token GitHub Secretsissa. 
- **Datarepo** `yt-chapters-data` (yksityinen, luot tämän itse): videoiden kuvaukset ja tekstitykset sekä botin tila ja loki. Botti kirjoittaa sinne, ja sinä muokkaat sitä.

Jako on tehty tietoturvan vuoksi. Datarepo ei sisällä YouTube-tunnuksia, joten sinne kirjoittava henkilö tai työkalu ei pääse siihen käsiksi. Vaikka julkisen repon workflow-ajojen lokit näkyvät kaikille, salaisuudet eivät näy. Koodirepoon kirjoittaa vain ylläpitäjä, ei botti eikä tekoäly.

Koodirepo on julkinen myös siksi, että botin ajot eivät silloin kuluta GitHub Actionsin minuuttikiintiötä.

Julkisesti näkyvät silti tämän repon koodi ja sen git-historia, ajojen ajankohdat ja se, onnistuiko ajo. Jos lisäät videon käsin (ks. [Komennot](#komennot)), videon tunniste voi näkyä ajon tiedoissa.

Alla olevissa ohjeissa `OMISTAJA` tarkoittaa GitHub-käyttäjätunnustasi. Korvaa se omallasi.

## Käyttö

1. (Sinä:) Pidä livelähetys normaaliin tapaan.
2. (YouTube:) Livelähetyksen päättyessä YouTube tekee sille tekstityksen. Tämä voi kestää 24 tuntia tai kauemmin.
3. (Botti:) Botti tarkistaa uudet livelähetykset tunnin välein. 
4. (Botti:) Botti lataa YouTubesta tekstityksen ja nykyisen kuvauksen ja pushaa ne yksityiseen datarepoon.
5. (Valinnainen:) Botti lähettää sähköpostin sinulle, kun push on valmis.
6. (Sinä:) Ota `git pull` datareposta ja avaa videon kansio, esimerkiksi `videos/2024-06-01-abc123/`.
7. (Sinä:) Muokkaa kuvausta (`description.txt`), esimerkiksi lisää aikaleimat.
8. (Sinä:) Tee `git commit -am "Aikaleimat"` ja `git push` datarepoon.
9. (Botti:) Botti tarkistaa kuvauksen ja julkaisee sen YouTubeen. Jos [asennuksen kohta 7](#7-valinnainen-julkaisu-heti-pushista) on tehty, julkaisu alkaa noin minuutin kuluessa pushista. Muuten kuvaus päivittyy seuraavalla ajolla, joka on tunnin välein.
10. (Valinnainen:) Jos haluat julkaista heti etkä ole tehnyt kohtaa 7, käynnistä botti käsin (ks. [Komennot](#komennot)).

### Mitä videokansio sisältää

Videon kansio on muotoa `videos/<pvm>-<videoID>/`. `<pvm>` on lähetyksen päättymispäivä, ja käsin lisätyllä (ks. [Komennot](#komennot)) videolla lisäyspäivä. Päivä on UTC-ajassa, joten Suomen iltana päättynyt lähetys voi saada edellisen päivän päivämäärän.

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

### Ohjeet kielimallille

Botti luo datarepoon myös `README.md`:n ja `CLAUDE.md`:n. Niiden ansiosta voit avata datarepon Claude Codessa ja pyytää esimerkiksi "tee aikaleimat uusimmalle videolle", ilman API-kuluja. Voit luonnollisesti tehdä itse oman ohjeen kielimallille ja poistaa CLAUDE.md:n. 

## Asennus

Asenna ensin

 * Git
 * `ssh-keygen` ja 
 * Python 3

Alla oletetaan, että `yt-chapters`-repo kloonataan kansioon `~/yt-chapters` ja YouTube-kirjautumistiedot pidetään kansiossa `~/yt-auth`.

### 1. Google Cloud

1. Mene osoitteeseen <https://console.cloud.google.com/>. Luo projekti ja ota käyttöön **YouTube Data API v3**.
2. Määritä OAuth consent screen: tyyppi *External*, lisää oma tilisi ja vaihda tilaksi *In production*. *Testing*-tilassa refresh token vanhenee 7 päivässä. Jos tilaa ei voi vaihtaa, katso [Vianetsintä](#vianetsintä).
3. Luo Credentials → OAuth client ID, tyyppi **Desktop app**, ja lataa `client_secret.json`. Tiedosto jää omalle koneellesi, eikä sitä viedä GitHubiin.

### 2. Datarepo ja sen avain

Luo GitHubiin uusi **yksityinen** repo (esim. `OMISTAJA/yt-chapters-data`). Jätä se täysin tyhjäksi, eli älä lisää README-, .gitignore- tai lisenssitiedostoa. Botti luo ensimmäisellä ajolla `main`-haaran sekä `README.md`:n ja `CLAUDE.md`:n. Valmiiksi olemassa olevaa README:tä se ei korvaa, eikä se luo kumpaakaan uudelleen, jos poistat sen.

Luo omalle koneelle hakemisto `~/yt-auth` ja siihen avain, jolla botti kirjoittaa datarepoon:

```bash
mkdir ~/yt-auth && chmod 700 ~/yt-auth
ssh-keygen -t ed25519 -N "" -C yt-chapters-actions -f ~/yt-auth/yt-chapters-deploy
cat ~/yt-auth/yt-chapters-deploy.pub
```

Lisää tulostettu julkinen avain datarepon kohtaan *Settings* → *Deploy keys* → *Add deploy key*. Anna *Title*-kenttään esimerkiksi `yt-chapters-actions`, liitä avain *Key*-kenttään ja valitse *Allow write access*. Nimi on tunniste, jolla avaimen löytää listasta myöhemmin. Yksityinen avain `~/yt-auth/yt-chapters-deploy` tarvitaan kohdassa 4. Ota talteen myös repon SSH-osoite (`git@github.com:...`).

### 3. YouTube-kirjautuminen

Forkkaa koodirepo ja kloonaa forkki omalle koneelle. Kirjautumistiedot pidetään kohdassa 2 luodussa hakemistossa `~/yt-auth`. Siellä ajetaan koodirepon skripti `auth.py`, joka tallentaa kirjautumistokenin `token.json`-tiedostoon.

```bash
git clone https://github.com/OMISTAJA/yt-chapters.git ~/yt-chapters
cd ~/yt-auth
cp ~/Downloads/client_secret_*.json client_secret.json
python3 -m venv venv
venv/bin/pip install google-auth-oauthlib
venv/bin/python ~/yt-chapters/auth.py
```

Komento on `python3`, ei `python`. Jos `python3` tai `venv` puuttuu, asenna ne ensin (Debianissa ja Ubuntussa `sudo apt install python3 python3-venv`). Virtuaaliympäristö `~/yt-auth/venv` tarvitaan, koska uudet Debian-pohjaiset jakelut eivät salli pip-asennuksia suoraan järjestelmän Pythoniin.

Avaa tulostunut URL selaimessa ja kirjaudu kanavan omistavalla tilillä. Kirjautuminen on valmis, kun komento tulostaa `Token tallennettu: token.json`.

`token.json` viedään kohdassa 4 GitHubiin. Säilytä hakemisto `~/yt-auth` (mutta poista `token.json`), sillä sitä tarvitaan, jos kirjautuminen joskus vanhenee.

### 4. Asetukset ja salaisuudet koodirepoon

Tee asetustiedosto kopioimalla koodirepon [`config.example.toml`](config.example.toml) ja muokkaamalla sitä:

```bash
cp ~/yt-chapters/config.example.toml ~/yt-auth/config.toml
chmod 600 ~/yt-auth/config.toml
```

Muuta tiedostosta ainakin nämä:

- `repo_url`: datarepon SSH-osoite (kohta 2).
- `start_after`: vain tämän (muodossa `YYYY-MM-DDTHH:MM:SSZ`, UTC-aika) jälkeen päättyneet lähetykset otetaan mukaan. Aseta asennuspäivä, ettei koko historia tule jonoon.
- `author_email`: esim. `yt-chapters@github-actions`. Tämä vaikuttaa vain datarepon committeihin.
- `context` (`[general]`-osiossa): kerro kielimallille, millaisista videoista on kyse. Tarvitaan vain, jos `[llm]` on käytössä.
- `[email]` (valinnainen): ilmoitukset uusista videoista, virheistä ja julkaisuista, ks. [Sähköposti-ilmoitukset](#sähköposti-ilmoitukset). Jos et halua ilmoituksia, poista osio.
- `[llm]` (valinnainen): Claude API kirjoittaa `ehdotus.txt`:n. Aseta `enabled = true` ja laita API-avain kenttään `api_key`.

Muut rivit jätetään ennalleen: `state_dir` ja `ssh_key` vastaavat polkuja, joita workflow käyttää.

Lisää sitten koodirepon (`OMISTAJA/yt-chapters`) salaisuuksiin nämä. Salaisuudet lisätään GitHubissa repon kohtaan **Settings → Secrets and variables → Actions → Secrets**. Salaisuuden arvoa ei voi lukea jälkikäteen, vain korvata uudella. Lisää kukin salaisuus klikkaamalla *New repository secret*.

| Secret            | Sisältö                                                                            |
| ----------------- | ---------------------------------------------------------------------------------- |
| `CONFIG_TOML`     | Tiedoston `~/yt-auth/config.toml` sisältö                                          |
| `YOUTUBE_TOKEN`   | Tiedoston `~/yt-auth/token.json` sisältö                                           |
| `DATA_DEPLOY_KEY` | Yksityisen avaimen `yt-chapters-deploy` koko sisältö, myös `BEGIN`- ja `END`-rivit |

Säilytä `~/yt-auth/config.toml`, koska asetuksia muutetaan tarvittaessa sen kautta: muokkaa tiedostoa ja korvaa secret `CONFIG_TOML` sen uudella sisällöllä. Poista sen sijaan tiedostot, joita ei enää tarvita. Niillä pääsee kanavaan ja datarepoon.

```bash
rm ~/yt-auth/token.json ~/yt-auth/yt-chapters-deploy ~/yt-auth/yt-chapters-deploy.pub
```

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

Sähköposti tulee testattua kohdassa 6. Jos viestiä ei tule, katso [Vianetsintä](#vianetsintä).

### 5. Workflow koodirepoon

Workflow-tiedosto [`.github/workflows/yt-chapters.yml`](.github/workflows/yt-chapters.yml) tulee forkin mukana, joten sitä ei tarvitse luoda. Sen sijaan forkin Actions pitää ottaa käyttöön, koska GitHub poistaa forkatun repon workflow't ja erityisesti niiden ajastuksen oletuksena käytöstä:

1. Avaa forkin **Actions**-välilehti. Jos GitHub kysyy, ajetaanko forkin workflow't, vastaa *I understand my workflows, go ahead and enable them*.
2. Valitse vasemmalta **yt-chapters**. Jos sivulla lukee, että workflow on poistettu käytöstä, paina *Enable workflow*.

Ajastus toimii vain repon oletushaarassa. Jos teet forkiin oman haaran, pidä workflow oletushaarassa.

Workflow toimii näin:

- Botin tila (`state.db`), tilalistaus (`tila.txt`) ja loki (`loki.txt`) säilyvät ajojen välillä datarepon `state`-haarassa, jonka workflow luo itse. Haarassa on aina yksi commit, jonka workflow korvaa joka ajolla.
- Salaisuudet kirjoitetaan ajon ajaksi runnerin hakemistoon `/var/lib/yt-chapters/`, ja ne katoavat ajon päätyttyä.
- GitHubin SSH-avain on kiinnitetty workflow'hun (sormenjälki `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`).

### 6. Kokeilu

1. Avaa koodirepossa **Actions → yt-chapters → Run workflow**.
2. Kirjoita kenttään `video_id` jonkin oman videosi tunniste. Videolla pitää olla tekstitys, ja se voi olla vanhakin.
3. Kun ajo on valmis, avaa datarepon `state`-haarasta tiedosto `tila.txt` (ks. [Komennot](#komennot)). Videon pitäisi olla tilassa `in_repo`.
4. Tarkista, että datarepon `main`-haaraan tuli videon kansio.
5. Jos sähköposti-ilmoitukset ovat käytössä, sinulle tulee viesti "Uusi video repossa".
6. Tarkista vielä koodirepon Actions-välilehdeltä, ettei **yt-chapters**-workflow'n sivulla ole ilmoitusta käytöstä poistetusta ajastuksesta (ks. kohta 5). Käsin käynnistetty ajo onnistuu, vaikka ajastus olisi pois päältä.

Tästä eteenpäin botti ajetaan tunnin välein.

### 7. (Valinnainen) Julkaisu heti pushista

Push datarepoon ei suoraan käynnistä workflow'ta koodirepossa. Siksi datarepoon lisätään pieni workflow, joka käynnistää botin. Tätä varten tarvitaan token, jolla voi **vain** käynnistää koodirepon workflow'n. Jos token vuotaa, sillä voi käynnistää tai pysäyttää botin ajoja, myös vieraalla `video_id`:llä, jolloin datarepoon voi tulla ylimääräisiä kansioita. Koodiin ja salaisuuksiin se ei pääse.

1. Luo token GitHubissa: oma profiili → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token.
   - *Repository access*: Only select repositories → `OMISTAJA/yt-chapters`
   - *Permissions*: **Actions: Read and write**. Muita oikeuksia ei valita (Metadata: Read-only tulee automaattisesti).
   - Voimassaoloaika on vapaa. Kun token vanhenee, botti toimii edelleen tunnin välein, mutta julkaisu ei enää käynnisty heti pushista.
2. Lisää token datarepon (`OMISTAJA/yt-chapters-data`) secretiksi nimellä `YT_CHAPTERS_TOKEN` (Settings → Secrets and variables → Actions → Secrets, kuten kohdassa 4).
3. Lisää datarepoon tiedosto `.github/workflows/julkaise.yml`:

```yaml
name: Käynnistä julkaisu

on:
  push:
    branches: [main]
    paths: ["videos/*/description.txt"]

permissions: {}

jobs:
  trigger:
    # Botin omat commitit eivät käynnistä uutta ajoa
    if: github.event.head_commit.author.name != 'yt-chapters'
    runs-on: ubuntu-latest
    steps:
      - run: gh workflow run yt-chapters.yml -R OMISTAJA/yt-chapters
        env:
          GH_TOKEN: ${{ secrets.YT_CHAPTERS_TOKEN }}
```

Ehdossa oleva `yt-chapters` on botin committien tekijä, eli `config.toml`:n `author_name`. Jos muutit sitä, muuta myös tätä.

Jos pushaat kuvauksia nopeasti peräkkäin, ajot jonoutuvat. Tämä ei haittaa, koska jokainen ajo käsittelee kaikki muutokset.

## Ylläpito

Botti pyörii koodirepon GitHub Actionsissa. Ajo alkaa joka tunti noin 17 minuuttia yli, mutta GitHubin ajastus voi myöhästyä ruuhkassa kymmeniä minuutteja.

**Minuutit:** Julkisen koodirepon ajot eivät kuluta Actions-minuutteja. Kohdan 7 käynnistys-workflow on yksityisessä datarepossa, joten se kuluttaa tilin kiintiötä noin minuutin pushia kohden. Kiintiö on tilikohtainen, eli sen jakavat kaikki tilin yksityiset repot. Ilmaistilillä minuutteja on 2000 kuukaudessa.

**Ajastuksen poistuminen käytöstä:** GitHub poistaa julkisen repon ajastetut workflow't käytöstä, jos repossa ei ole ollut toimintaa 60 päivään. Botti kirjoittaa vain datarepoon, joten koodirepo voi hiljentyä. Ajastuksen saa takaisin päälle koodirepon Actions-välilehdeltä (yt-chapters → *Enable workflow*), ja sen poistumisen voi estää pushaamalla koodirepoon jotain 60 päivän välein.

### Missä mikäkin on

| Paikka                  | Sisältö                                                                                                                                                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Koodirepo, oletushaara  | `yt_chapters.py` ja `.github/workflows/yt-chapters.yml`                                                                                                                                                                      |
| Koodirepo, Secrets      | `CONFIG_TOML`, `YOUTUBE_TOKEN`, `DATA_DEPLOY_KEY`                                                                                                                                                                            |
| Koodirepo, Actions      | Ajojen onnistuminen. Julkisissa lokeissa ei ole videoiden tietoja.                                                                                                                                                           |
| Datarepo, `main`        | Kuvaukset. Lisäksi valinnaisesti `.github/workflows/julkaise.yml` ja secret `YT_CHAPTERS_TOKEN`.                                                                                                                             |
| Datarepo, `state`-haara | `state.db` (botin tila), `tila.txt` (videoiden tila) ja `loki.txt` (botin loki, noin 5000 viimeistä riviä). Älä muokkaa tai poista haaraa: tyhjästä tilasta aloittava botti kirjoittaisi julkaisemattomien kuvausten päälle. |
| Oma kone, `~/yt-auth/`  | `config.toml` sekä `client_secret.json` uudelleenkirjautumista varten                                                                                                                                                        |

### Komennot

Botti käynnistetään käsin koodirepon kohdasta **Actions → yt-chapters → Run workflow**:

- **Aja heti** ajastusta odottamatta: jätä `video_id` tyhjäksi. Ajo julkaisee pushatut kuvaukset ja hakee uudet lähetykset ja tekstitykset.
- **Lisää video** tai hae sen tekstitys uudelleen: kirjoita videon tunniste kenttään `video_id`. Video lisätään ja käsitellään samassa ajossa. Jos video on jo repossa, botti hakee tekstityksen uudelleen mutta ei kirjoita julkaisemattomien muokkauksien päälle, ja pushatut kuvausmuutokset julkaistaan samassa ajossa. Koodirepo on julkinen, joten tunniste voi näkyä ajon tiedoissa.

`VIDEO_ID` on videon tunniste osoitteessa `https://youtu.be/VIDEO_ID`.

Tila ja loki luetaan datarepon `state`-haarasta. GitHubissa valitse datarepon haaravalikosta `state` ja avaa tiedosto. Komentorivillä datarepon kloonissa:

```bash
git fetch origin state
git show origin/state:tila.txt              # seuratut videot ja niiden tila
git show origin/state:loki.txt | tail -50   # botin loki
```

`tila.txt` näyttää kunkin videon tilan:

- `waiting`: odottaa tekstitystä.
- `in_repo`: video on repossa, ja `description.txt`:n muutokset julkaistaan.
- `failed`: botti luovutti. Syy näkyy rivin lopussa.

Jos julkaisu estyy, botti kirjoittaa syyn videon kansioon ja lähettää sähköpostin, jos ilmoitukset ovat käytössä. Jos koko ajo epäonnistuu, GitHub lähettää siitä sähköpostin (Settings → Notifications → Actions), ja syy löytyy `loki.txt`:stä.

### Päivitys

- **Koodi:** push koodirepon oletushaaraan riittää. Uusi versio on käytössä seuraavalla ajolla.
- **Asetukset:** muokkaa tiedostoa `~/yt-auth/config.toml` ja korvaa secret `CONFIG_TOML` sen sisällöllä. Jos `config.example.toml`:ään tuli uusia asetuksia, lisää ne käsin.
- **Salaisuudet:** korvaa secret uudella arvolla samalla nimellä.

## Vianetsintä

Jos ajo epäonnistuu jo ennen botin käynnistymistä, syy näkyy koodirepon Actions-lokissa, esimerkiksi vaiheessa *Palauta tila ja salaisuudet*. Muuten syy on datarepon `state`-haaran tiedostossa `loki.txt`.

| Oire                                                                                                                    | Mitä tehdä                                                                                                                                                                                                                                           |
| ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Kuvaus ei päivity pushin jälkeen                                                                                        | Aja datarepossa `git pull` ja katso, onko videon kansiossa `VIRHEET.txt` tai `description.youtube.txt`. Jos kumpaakaan ei ole, katso `loki.txt`. Jos käytössä on kohta 7, katso myös datarepon Actions-välilehti.                                    |
| Kuvaus päivittyy vasta tunnin päästä, vaikka kohta 7 on tehty                                                           | Datarepon ajo *Käynnistä julkaisu* epäonnistui. Jos lokissa on `HTTP 401` tai `403`, token on vanhentunut tai sen oikeudet ovat väärät. Luo uusi token ja päivitä secret `YT_CHAPTERS_TOKEN`.                                                        |
| Push datarepoon hylätään                                                                                                | Botti pushasi välissä. Aja `git pull --rebase` ja pushaa uudelleen.                                                                                                                                                                                  |
| Actions-lokissa `Permission denied (publickey)`                                                                         | `DATA_DEPLOY_KEY` ei vastaa datarepon deploy keytä, tai Allow write access puuttuu. Luo uusi avainpari kuten kohdassa 2.                                                                                                                             |
| Actions-lokissa `TOMLDecodeError` tai `KeyError`                                                                        | `CONFIG_TOML` on virheellinen tai siitä puuttuu kenttä. Vertaa `~/yt-auth/config.toml`:ää `config.example.toml`:ään ja korvaa secret.                                                                                                                |
| Ajastetut ajot eivät käynnisty                                                                                          | Tarkista, että workflow on oletushaarassa ja että Actions on päällä (Settings → Actions). Forkissa ajastus on oletuksena pois päältä, ks. [kohta 5](#5-workflow-koodirepoon). Jos workflow on poistettu käytöstä toimettomuuden vuoksi, ks. [Ylläpito](#ylläpito). GitHubin ajastus voi myös myöhästyä ruuhkassa.                        |
| Uusi lähetys ei tule repoon                                                                                             | Katso `tila.txt`. Tila `waiting` tarkoittaa, että tekstitys ei ole vielä valmis. Jos videota ei ole listalla, se luultavasti päättyi ennen `start_after`-aikaa: lisää se kentällä `video_id`.                                                        |
| Videon tila on `failed`                                                                                                 | Tekstitystä ei löytynyt 72 tunnissa, tai vienti repoon epäonnistui kolmesti. Korjaa syy ja aja workflow kentällä `video_id`.                                                                                                                         |
| Sähköposti "YouTube-kirjautuminen vanhentunut" tai `loki.txt`:ssä `RefreshError`                                        | Kirjaudu uudelleen omalla koneella: aja hakemistossa `~/yt-auth` komento `python3 ~/yt-chapters/auth.py` kuten [kohdassa 3](#3-youtube-kirjautuminen). Korvaa sitten secret `YOUTUBE_TOKEN` uudella `token.json`:lla ja poista tiedosto. |
| Sähköposteja ei tule                                                                                                    | Etsi `loki.txt`:stä rivi `ilmoituksen lähetys epäonnistui` ja katso sen alla oleva virhe seuraavista riveistä. Tarkista myös, että `[email]`-osiossa on `enabled = true`.                                                                            |
| `loki.txt`:ssä `534 5.7.9 Application-specific password required`                                                       | `password`-kentässä on tilin tavallinen salasana. Vaihda tilalle sovellussalasana ja korvaa secret `CONFIG_TOML`.                                                                                                                                    |
| `loki.txt`:ssä `535 Username and Password not accepted`                                                                 | Sovellussalasana on väärin, tai se on poistettu. Luo uusi sovellussalasana, laita se `password`-kenttään ja korvaa secret `CONFIG_TOML`.                                                                                                             |
| Sähköpostin lähetys päättyy aikakatkaisuun                                                                              | Yhteys porttiin 465 ei toimi. Kokeile asetuksia `smtp_port = 587` ja `smtp_starttls = true`.                                                                                                                                                         |
| OAuth consent screenin tilaa ei voi vaihtaa Testingistä "In production" -tilaan ([asennuksen kohta 1](#1-google-cloud)) | Täytä ensin consent screenin tiedoista sovelluksen nimi (*App name*), kotisivun osoite (*Application home page*) ja tietosuojaselosteen osoite (*Application privacy policy link*).                                                                  |
