import json
import os
from functools import partial
from os import mkdir
from os.path import join, splitext
from collections import namedtuple

def is_osx():
    import platform
    return platform.system() == 'Darwin'


def extract_name(path):
    return splitext(path)[0]

AudioParams = namedtuple('AudioParams', 'nchannels sampwidth framerate nframes comptype compname')
audio_ext = '.wav'

if is_osx():
    audio_ext = '.aifc'

class SpeechAnalysis(object):
    def __init__(self, filename=None):
        self.audio = None
        self.audio_params = None
        if filename:
            self.from_audio(filename)

    def __del__(self):
        if self.audio:
            self.audio.close()

    def _get_audio(self, filename):
        if filename.endswith('.aifc'):
            import aifc as wave
        elif filename.endswith('.wav'):
            import wave
        else:
            raise Exception('Unknown file extension: ' + filename)
        return wave.open(filename)

    def from_audio(self, filename):
        self.audio = self._get_audio(filename)
        self.audio_params = AudioParams(self.audio.getparams())

    def extract_specgram_for_frame(self, frame, pad_frames=128):
        if not self.audio:
            raise Exception('No audio loaded')
        if frame < 0 or frame >= self.audio_params.nframes:
            raise Exception('No such frame')
        from matplotlib.mlab import specgram
        start = frame - pad_frames
        end = frame + pad_frames
        pad_start = 0
        pad_end = 0
        if start < 0:
            pad_start = -start
            start = 0
        if end > self.audio_params.nframes:
            pad_end = end - self.audio_params.nframes
            end = self.audio_params.nframes - 1
        frames_to_read = end - start
        self.audio.setpos(start)
        print('PS: %s\tFR: %s\tPE: %s' % (pad_start, frames_to_read, pad_end))
        frames = bytearray('\x00' * pad_start)
        frames.extend(bytearray(self.audio.readframes(frames_to_read)))
        frames.extend(bytearray('\x00' * pad_end))
        return frames

    def generate_specgrams(self, pad_frames=256):
        if not self.audio:
            raise Exception('No audio loaded')
        from matplotlib.mlab import specgram

        (nchannels, sampwidth, framerate, nframes, comptype, compname) = self.audio_params
        for cur_frame in xrange(nframes):
            yield nframes, cur_frame, self.extract_specgram_for_frame(cur_frame, pad_frames=pad_frames)


def generate_wav_file(from_text):
    from subprocess import call
    wav_name = splitext(from_text)[0] + audio_ext
    if is_osx:
        args = ['say', '-o', wav_name, '-f', from_text]
    else:
        args = ['espeak', '-f', from_text, '-w', wav_name]
    print('building', wav_name)
    call(args)


def generate_dat_file(from_wav):
    dat_name = splitext(from_wav)[0] + '.dat'
    print('reading', from_wav)
    sa = SpeechAnalysis(from_wav)
    last_percent = 0
    for total, frame, spec in sa.generate_specgrams():
        if int(frame * 100 / total) != last_percent:
            print last_percent
            last_percent = int(frame * 100 / total)
        frames[frame] = map(lambda a: a.tolist(), spec)
        if frame > 10000:
            print('read', frame, 'frames')
            break
    with open(dat_name, 'w') as dat_file:
        import json
        dat_file.write(json.dumps(frames))


def init_files(in_path='training'):
    return map(partial(join, in_path), os.listdir(in_path))


def build_wav_files():
    files = init_files()
    text_files = sorted(filter(lambda f: f.endswith('.txt'), files))
    wav_files = sorted(filter(lambda f: f.endswith(audio_ext), files))
    generate_missing_files(text_files, wav_files, generate_wav_file, ext='.txt')


def build_dat_files():
    files = init_files()
    wav_files = sorted(filter(lambda f: f.endswith(audio_ext), files))
    dat_files = sorted(filter(lambda f: f.endswith('.dat'), files))
    generate_missing_files(wav_files, dat_files, generate_dat_file, ext=audio_ext)


def generate_missing_files(expected, actual, fn, ext='.txt'):
    if len(expected) != len(actual):
        diff = set(map(extract_name, expected)) - set(map(extract_name, actual))
        for txt in diff:
            fn(txt + ext)


build_wav_files()
build_dat_files()
