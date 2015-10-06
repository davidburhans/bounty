import json
import os
from functools import partial
from os import mkdir
from os.path import join, splitext


def extract_name(path):
    return splitext(path)[0]


def generate_specgrams(from_wav, window_size=256):
    import wave
    from matplotlib.mlab import specgram
    wav = wave.open(from_wav)
    (nchannels, sampwidth, framerate, nframes, comptype, compname) = wav.getparams()
    while wav.tell() < nframes:
        yield nframes, wav.tell(), specgram(bytearray(wav.readframes(256)))
    wav.close()


def generate_wav_file(from_text):
    from subprocess import call
    wav_name = splitext(from_text)[0] + '.wav'
    args = ['espeak', '-f', from_text, '-w', wav_name]
    print('building', wav_name)
    call(args)


def generate_dat_file(from_wav):
    dat_name = splitext(from_wav)[0] + '.dat'
    print('reading', from_wav)
    frames = {}
    last_percent = 0
    for total, frame, spec in generate_specgrams(from_wav):
        if int(frame * 100 / total) != last_percent:
            print last_percent
            last_percent = int(frame * 100 / total)
        frames[frame] = map(lambda a: a.tolist(), spec)


def init_files(in_path='training'):
    return map(partial(join, in_path), os.listdir(in_path))


def build_wav_files():
    files = init_files()
    text_files = sorted(filter(lambda f: f.endswith('.txt'), files))
    wav_files = sorted(filter(lambda f: f.endswith('.wav'), files))
    generate_missing_files(text_files, wav_files, generate_wav_file, ext='.txt')


def build_dat_files():
    files = init_files()
    wav_files = sorted(filter(lambda f: f.endswith('.wav'), files))
    dat_files = sorted(filter(lambda f: f.endswith('.dat'), files))
    generate_missing_files(wav_files, dat_files, generate_dat_file, ext='.wav')


def generate_missing_files(expected, actual, fn, ext='.txt'):
    if len(expected) != len(actual):
        diff = set(map(extract_name, expected)) - set(map(extract_name, actual))
        for txt in diff:
            fn(txt + ext)


build_wav_files()
build_dat_files()
