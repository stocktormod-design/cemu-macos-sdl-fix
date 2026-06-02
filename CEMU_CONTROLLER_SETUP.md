# 8BitDo Ultimate 2C Wireless + Cemu på Mac — hva som faktisk funker

## Det som **ikke** funker godt (hos deg / på Mac)

| Metode | Hvorfor |
|--------|---------|
| Modus-knapper (B+Home osv.) | Finnes ikke på Ultimate 2C Wireless |
| **Steam Input** | Injecter ofte **ikke** i native Mac-apps som Cemu Metal |
| **Enjoyable** | Sticks blir on/off, ikke analog |
| **SDL direkte** | Ofte ingen/for dårlig støtte på BT |
| **2.4G uten adapter** | Dongle er USB-A — trenger USB-C adapter på Mac |
| **DSU .app / GUI** | For tungt på batteri, mange bugs |

## Det som **funker** (analog sticks)

**Minimal DSU bridge** — bare mens du spiller, i terminal. Ingen skjult Python etterpå.

### Steg 1 — Test at Mac ser kontrolleren

```bash
python3 /Users/tormodholand/CEMU/scripts/test_controller.py
```

Du skal se `stick: x=... y=...` endre seg når du beveger venstre stick.

### Steg 2 — Spilløkt

```bash
/Users/tormodholand/CEMU/scripts/cemu_play.sh
```

1. Script starter lett bridge (20 FPS, `--light`)
2. Åpner Cemu
3. I Cemu: **DSUController**, **Controller 2**, `127.0.0.1:26760`, profil **8bitdo_dsu_auto**
4. Map én gang hvis nødvendig
5. Når du er ferdig: **Enter** i terminalen → bridge stopper

Logg ved feil: `/tmp/8bitdo_bridge_session.log`

### Hvis ingen input i Cemu

1. Åpne **Input settings** mens bridge kjører
2. Velg **Controller 2** på nytt i dropdown (tvinger DSU subscribe)
3. Ikke start Steam samtidig

### Stopp alt

```bash
/Users/tormodholand/CEMU/scripts/stop_bridge.sh
```

## Hardware som kan gjøre livet enklere

- **USB-A → USB-C adapter** (~50 kr) + 2.4G dongle → test SDL/bridge igjen (ofte stabilere enn BT)
- **USB-C kabel** til pad hvis du har den

## Gyro (BOTW)

I `cemu_play.sh` er gyro av for batteri. For gyro, start bridge manuelt:

```bash
python3 archive/dsu_bridge_experiment/8bitdo_dsu_bridge.py --slot 2 --fps 20 --light --gyro-source stick
```
