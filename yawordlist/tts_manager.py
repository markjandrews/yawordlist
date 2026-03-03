import pathlib

import io
import hashlib
import wave
import winsound

from piper import PiperVoice, SynthesisConfig


class TTSManager:
    def __init__(
        self,
        model_path: str,
        cache_dir: str | pathlib.Path = "audio_cache",
        syn_config: SynthesisConfig | None = None,
        debug: bool = False,
    ):
        self.model_path = model_path
        self.cache_dir = pathlib.Path(cache_dir)
        self.syn_config = syn_config or SynthesisConfig()
        self.debug = debug
        self._voice: PiperVoice | None = None

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, bytes] = {}

    @property
    def voice(self) -> PiperVoice:
        if self._voice is None:
            self._voice = PiperVoice.load(self.model_path)
        return self._voice

    def _hash_text(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _cache_path(self, text: str) -> pathlib.Path:
        return self.cache_dir / f"{self._hash_text(text)}.wav"

    def _synthesize_to_wav_bytes_and_file(self, text: str, wav_path: pathlib.Path) -> bytes:
        wav_bytes = io.BytesIO()
        first_chunk = True
        with (
            wave.open(wav_bytes, "wb") as mem_wav,
            wave.open(str(wav_path), "wb") as file_wav,
        ):
            for chunk in self.voice.synthesize(text, syn_config=self.syn_config):
                if first_chunk:
                    for wav_file in (mem_wav, file_wav):
                        wav_file.setnchannels(chunk.sample_channels)
                        wav_file.setsampwidth(chunk.sample_width)
                        wav_file.setframerate(chunk.sample_rate)
                    first_chunk = False

                mem_wav.writeframes(chunk.audio_int16_bytes)
                file_wav.writeframes(chunk.audio_int16_bytes)

        return wav_bytes.getvalue()

    def _get_wav_data(self, text: str) -> bytes:
        key = self._hash_text(text)
        source = "memory"

        # 1) in-memory cache
        wav_data = self._memory_cache.get(key)

        # 2) file cache -> load into memory
        if wav_data is None:
            source = "file"
            wav_path = self.cache_dir / f"{key}.wav"
            if wav_path.exists():
                wav_data = wav_path.read_bytes()
                self._memory_cache[key] = wav_data

        # 3) synthesize -> write to file + memory
        if wav_data is None:
            source = "synth"
            wav_path = self.cache_dir / f"{key}.wav"
            wav_data = self._synthesize_to_wav_bytes_and_file(text, wav_path)
            self._memory_cache[key] = wav_data

        if self.debug:
            print(f"tts cache={source} text={text!r}")

        return wav_data

    def warm_cache(self, phrases: list[str]) -> None:
        for text in phrases:
            self._get_wav_data(text)

    def speak(self, text: str) -> None:
        wav_data = self._get_wav_data(text)

        # 4) play memory-cached audio
        winsound.PlaySound(wav_data, winsound.SND_MEMORY)


if __name__ == "__main__":
    SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

    syn_config = SynthesisConfig(
        length_scale=1.25,
        normalize_audio=False,
    )

    tts = TTSManager(
        model_path=str(SCRIPT_DIR / "tts" / "en_US-libritts-high.onnx"),
        syn_config=syn_config,
        debug=True,
    )
    tts.speak("spaceship")
    tts.speak("constellation")
    tts.speak("attempt 27")
    tts.speak("word 19")
