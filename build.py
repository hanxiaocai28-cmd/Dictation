#!/usr/bin/env python3
"""
Builds the data files the dictation page reads.

  python build.py vocabulary.csv            -> writes words.js and audio/manifest.js
  python build.py vocabulary.csv --audio    -> also creates any missing MP3s with Google Cloud TTS

Audio files live in audio/ and are named after the word, e.g. audio/老师.mp3.
Anything you record yourself and save under that name is picked up the same way,
and a file that already exists is never overwritten, so your recordings win.

Google setup (only needed for --audio):
  pip install google-cloud-texttospeech
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(HERE, "audio")

# Voice used for every clip. Audition a few in Google's demo and change this if you prefer another.
VOICE = "cmn-CN-Wavenet-A"
SPEAKING_RATE = 0.9

# Force a reading for polyphonic characters: word -> pinyin with tone numbers (5 = neutral).
# Example: "佛蒙特": "fo2 meng2 te4"
OVERRIDES = {
}

def written_form(chars):
    """What students write and hear: drop optional 儿 like 玩(儿); keep other optional parts like (飞)机场."""
    s = re.sub(r"\s", "", chars)
    s = re.sub(r"[（(]儿[）)]", "", s)
    return re.sub(r"[（）()]", "", s)

def is_awkward(chars):
    """Skip entries that aren't plain words: grammar patterns (太…了) or mixed scripts (T恤衫)."""
    return bool(re.search(r"[^\u4e00-\u9fff]", written_form(chars)))

def load(csv_path):
    words, skipped = [], []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            c = row["characters"].strip()
            if not c:
                continue
            if is_awkward(c):
                skipped.append(c)
                continue
            lesson = row.get("lesson", "").strip()
            words.append({
                "c": c, "w": written_form(c), "p": row["pinyin"].strip(),
                "pos": row.get("part_of_speech", "").strip(), "en": row.get("english", "").strip(),
                "l": int(lesson) if lesson.isdigit() else 0,
            })
    return words, skipped

def make_audio(words):
    from google.cloud import texttospeech as tts
    client = tts.TextToSpeechClient()
    voice = tts.VoiceSelectionParams(language_code="cmn-CN", name=VOICE)
    cfg = tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3, speaking_rate=SPEAKING_RATE)
    made = 0
    for w in {x["w"] for x in words}:
        path = os.path.join(AUDIO_DIR, w + ".mp3")
        if os.path.exists(path):
            continue
        if w in OVERRIDES:
            inp = tts.SynthesisInput(ssml=f'<speak><phoneme alphabet="pinyin" ph="{OVERRIDES[w]}">{w}</phoneme></speak>')
        else:
            inp = tts.SynthesisInput(text=w)
        audio = client.synthesize_speech(input=inp, voice=voice, audio_config=cfg).audio_content
        with open(path, "wb") as f:
            f.write(audio)
        made += 1
        print("  made", w)
    print(f"Created {made} new clips.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--audio", action="store_true", help="generate missing MP3s with Google Cloud TTS")
    a = ap.parse_args()

    words, skipped = load(a.csv)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    if a.audio:
        make_audio(words)

    with open(os.path.join(HERE, "words.js"), "w", encoding="utf-8") as f:
        f.write("window.WORDS = " + json.dumps(words, ensure_ascii=False, separators=(",", ":")) + ";\n")

    have = sorted(fn[:-4] for fn in os.listdir(AUDIO_DIR) if fn.endswith(".mp3"))
    with open(os.path.join(AUDIO_DIR, "manifest.js"), "w", encoding="utf-8") as f:
        f.write("window.AUDIO_FILES = " + json.dumps(have, ensure_ascii=False) + ";\n")

    missing = len({x["w"] for x in words} - set(have))
    print(f"{len(words)} words written, {len(skipped)} skipped: {'、'.join(skipped)}")
    print(f"{len(have)} audio files found, {missing} words still without audio.")

if __name__ == "__main__":
    sys.exit(main())
