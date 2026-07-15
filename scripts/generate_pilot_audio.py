#!/usr/bin/env python3
"""Generate a short Polish spoken audio sample for offline ASR pilot runs."""

from pathlib import Path

from gtts import gTTS

TEXT = (
    "Cześć, tu Maciej. Dziś pokażę domowy trening z kettlebell. "
    "Zaczynamy od rozgrzewki barków przez dwie minuty. "
    "Potem robimy trzy serie swingów po piętnaście powtórzeń. "
    "Między seriami odpoczywamy czterdzieści pięć sekund. "
    "Na koniec dodajemy goblet squat i krótkie rozciąganie bioder. "
    "Pamiętajcie o napięciu brzucha i równym oddechu."
)


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "examples" / "pilot_pl_no_captions.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    gTTS(text=TEXT, lang="pl").save(str(out))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()