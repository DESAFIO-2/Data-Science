import { Platform } from 'react-native';

let voicesListenerAttached = false;

/** Precarrega a lista de vozes do navegador (necessário no Chrome para evitar voz padrão em inglês). */
export function warmUpPtBrVoices(): void {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
  const synth = window.speechSynthesis;
  synth.getVoices();
  if (!voicesListenerAttached && typeof synth.addEventListener === 'function') {
    voicesListenerAttached = true;
    synth.addEventListener('voiceschanged', () => {
      synth.getVoices();
    });
  }
}

function scorePtVoice(voice: SpeechSynthesisVoice): number {
  const lang = (voice.lang || '').toLowerCase().replace('_', '-');
  if (!lang.startsWith('pt')) return -1;

  let score = lang.startsWith('pt-br') ? 50 : 10;
  const name = (voice.name || '').toLowerCase();

  if (name.includes('google') && (name.includes('brasil') || name.includes('portugu'))) score += 100;
  if (name.includes('francisca') || name.includes('thalita') || name.includes('antonio')) score += 85;
  if (name.includes('luciana') || name.includes('felipe')) score += 60;
  if (name.includes('natural') || name.includes('neural') || name.includes('enhanced') || name.includes('premium')) {
    score += 30;
  }
  if (!voice.localService) score += 20;
  return score;
}

/** Seleciona a melhor voz brasileira disponível no navegador (nunca retorna voz em inglês). */
export function pickBestPtBrVoice(): SpeechSynthesisVoice | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || !('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  let best: SpeechSynthesisVoice | null = null;
  let bestScore = -1;
  for (const voice of voices) {
    const score = scorePtVoice(voice);
    if (score > bestScore) {
      bestScore = score;
      best = voice;
    }
  }
  return best;
}

export function stopBrowserSpeech(): void {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
}

export function speakWithBrowserPtBr(
  text: string,
  opts?: { rate?: number; pitch?: number; onEnd?: () => void },
): boolean {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || !('speechSynthesis' in window)) {
    opts?.onEnd?.();
    return false;
  }
  const clean = text.trim();
  if (!clean) {
    opts?.onEnd?.();
    return false;
  }

  warmUpPtBrVoices();
  window.speechSynthesis.cancel();

  const utter = new SpeechSynthesisUtterance(clean);
  const ptVoice = pickBestPtBrVoice();
  if (ptVoice) {
    utter.voice = ptVoice;
    utter.lang = ptVoice.lang;
  } else {
    utter.lang = 'pt-BR';
  }
  utter.rate = opts?.rate ?? 1.02;
  utter.pitch = opts?.pitch ?? 1.02;

  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    opts?.onEnd?.();
  };
  utter.onend = done;
  utter.onerror = done;
  window.speechSynthesis.speak(utter);
  return true;
}

export function playNeuralAudioOrFallback(params: {
  text: string;
  audioBase64?: string | null;
  mimeType?: string;
  audioElRef: { current: HTMLAudioElement | null };
  rate?: number;
  onStartNeural?: () => void;
  onFallbackBrowser?: (voiceName: string | null) => void;
  onEnd: () => void;
}): void {
  const { text, audioBase64, mimeType, audioElRef, rate, onStartNeural, onFallbackBrowser, onEnd } = params;

  if (Platform.OS !== 'web') {
    onEnd();
    return;
  }

  stopBrowserSpeech();
  if (audioElRef.current) {
    try {
      audioElRef.current.onended = null;
      audioElRef.current.onerror = null;
      audioElRef.current.pause();
    } catch {
      // Ignora erro ao encerrar áudio anterior.
    }
  }

  const runBrowserFallback = () => {
    const picked = pickBestPtBrVoice();
    onFallbackBrowser?.(picked?.name ?? 'Web Speech pt-BR');
    speakWithBrowserPtBr(text, { rate, onEnd });
  };

  if (audioBase64 && typeof Audio !== 'undefined') {
    try {
      const audio = audioElRef.current ?? new Audio();
      audioElRef.current = audio;
      audio.src = `data:${mimeType || 'audio/mpeg'};base64,${audioBase64}`;
      audio.playbackRate = 1.0;

      let settled = false;
      const done = () => {
        if (settled) return;
        settled = true;
        onEnd();
      };
      audio.onended = done;
      audio.onerror = () => {
        if (settled) return;
        settled = true;
        runBrowserFallback();
      };

      onStartNeural?.();
      void audio.play().catch(() => {
        if (!settled) {
          settled = true;
          runBrowserFallback();
        }
      });
      return;
    } catch {
      // Fallback abaixo se HTML5 Audio falhar.
    }
  }

  runBrowserFallback();
}
