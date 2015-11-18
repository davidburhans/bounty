import json
import os
from functools import partial
from os import mkdir
from os.path import join, splitext
from collections import namedtuple

from bounty import (
    is_osx,
    extract_name,
    DEFAULT_TIME_SKIP,
    DEFAULT_PADDING,
    DEFAULT_FRAME_SKIP,
    )

import pylab


AudioParams = namedtuple('AudioParams', 'nchannels sampwidth framerate nframes comptype compname')
AUDIO_EXT = '.wav'

# http://dsp.stackexchange.com/questions/22442/ffmpeg-audio-filter-pipeline-for-speech-enhancement
ffmpeg_filters = ['highpass=frequency=300',
                  'lowpass=frequency=4000',
                  'bass=frequency=100:gain=-50',
                  'bandreject=frequency=200:width_type=h:width=200',
                  'compand=attacks=.05:decays=.05:points=-90/-90 -70/-90 -15/-15 0/-10:soft-knee=6:volume=-70:gain=10'
                  ]


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
        print('loading', filename)
        if filename.endswith('.wav'):
            import wave
        else:
            raise Exception('Unknown file extension: ' + filename)
        return wave.open(filename)

    def from_audio(self, filename):
        self.filename = filename
        self.audio = self._get_audio(filename)
        self.audio_params = AudioParams(*self.audio.getparams())

    def extract_specgram_data_for_frame(self, frame, pad_frames):
        if not self.audio:
            raise Exception('No audio loaded')
        if frame < 0 or frame >= self.audio_params.nframes:
            raise Exception('No such frame')
        from matplotlib.mlab import specgram
        pad_frames *= self.audio_params.nchannels
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
        frames = bytearray('\x00' * self.audio_params.sampwidth * pad_start)
        frames.extend(bytearray(self.audio.readframes(frames_to_read)))
        frames.extend(bytearray('\x00' * self.audio_params.sampwidth * pad_end))
        return frames

    def get_specgram_figure_for_frame(self, frame, pad_seconds=DEFAULT_PADDING):
        return self.get_raw_specgram_for_frame(frame, pad_seconds=pad_seconds)[3].get_figure()

    def get_raw_specgram_for_frame(self, frame, pad_seconds=DEFAULT_PADDING):
        if pad_seconds:
            pad_frames = int(self.audio_params.framerate * pad_seconds)
        (nchannels, sampwidth, framerate, nframes, comptype, compname) = self.audio_params
        raw_data = self.extract_specgram_data_for_frame(frame=frame, pad_frames=pad_frames)
        data = pylab.frombuffer(raw_data, 'Int' + str(8 * self.audio_params.sampwidth))
        min_frame = max(0, frame - pad_frames)
        max_frame = min(frame + pad_frames, nframes)
        audio_pos = frame * 1.0 / framerate
        audio_min = max(0, audio_pos - pad_seconds)
        audio_max = min(audio_pos + pad_seconds, nframes * 1.0 / framerate)
        pylab.figure(num=None, figsize=(8, 6))
        pylab.subplot(111)
        pylab.title('Spectrogram of {0}: {1:04.5f} - {2:04.5f} s'.format(self.filename, audio_min, audio_max))
        pylab.suptitle('Frames {0:09d} - {1:09d}'.format(min_frame, max_frame))
        # results = pyfigaxes.specgram(data, Fs=self.audio_params.framerate)
        return pylab.specgram(data, Fs=framerate, NFFT=1024, noverlap=512)

    def generate_specgrams(self, pad_seconds=DEFAULT_PADDING, time_skip=DEFAULT_TIME_SKIP):
        for cur_frame in self.time_step(time_skip=time_skip):
            yield self.get_raw_specgram_for_frame(cur_frame, pad_seconds=pad_seconds)

    def frame_step(self, frame_skip=DEFAULT_FRAME_SKIP):
        if not self.audio:
            raise Exception('No audio loaded')
        (nchannels, sampwidth, framerate, nframes, comptype, compname) = self.audio_params
        for cur_frame in xrange(0, nframes, frame_skip):
            yield cur_frame

    def time_step(self, time_skip=DEFAULT_TIME_SKIP):
        if not self.audio:
            raise Exception('No audio loaded')
        (nchannels, sampwidth, framerate, nframes, comptype, compname) = self.audio_params
        frame_step = int(framerate * time_skip)
        for cur_frame in self.frame_step(frame_skip=frame_step):
            yield cur_frame

    def animate_specgram(self, pad_seconds=DEFAULT_PADDING, time_skip=DEFAULT_TIME_SKIP):
        import pylab
        prev = None
        for cur_frame in self.time_step(time_skip=time_skip):
            spec = self.get_specgram_figure_for_frame(cur_frame, pad_seconds=pad_seconds)
            spec.show()
            if prev:
                pylab.close(prev)
            prev = spec
        pylab.close(prev)


class SpeechHelper(object):
    @staticmethod
    def generate_wav_file(from_text, is_file=True):
        import time
        import uuid
        from subprocess import call
        uid = str(uuid.uuid4())
        wav_name = uid
        if is_file:
            wav_name = splitext(from_text)[0]

        wav_name = wav_name + AUDIO_EXT
        if is_osx:
            osx_snd = splitext(wav_name)[0] + '.aiff'
            if is_file:
                args = [['say', '-o', osx_snd, '-f', from_text,]]
            else:
                args = [['say', '-o', osx_snd, from_text]]
            args.append(['ffmpeg', '-y', '-i', osx_snd, wav_name,])
            args.append(['rm', osx_snd])
        else:
            if is_file:
                args = [['espeak', '-f', from_text, '-w', wav_name]]
            else:
                args = [['espeak', '-w', wav_name, from_text]]
        print('building', wav_name)
        for a in args:
            print('calling', a)
            call(a)
        return wav_name

    @staticmethod
    def str_to_wav(str_to_render):
        return SpeechHelper.generate_wav_file(str_to_render, is_file=False)

    @staticmethod
    def apply_audio_filter(wav_name, ffmpeg_filters=ffmpeg_filters, output=None):
        from subprocess import call
        if not output:
            output = wav_name
        if ffmpeg_filters:
            call(['ffmpeg', '-i', wav_name, '-f', 'wav', '-af', ',\n'.join(ffmpeg_filters), '-y', output])

    def __init__(self, path='training'):
        self.files = map(partial(join, in_path), os.listdir(in_path))

    def bulk_txt_to_wav(self):
        text_files = sorted(filter(lambda f: f.endswith('.txt'), self.files))
        wav_files = sorted(filter(lambda f: f.endswith(AUDIO_EXT), self.files))
        self.generate_missing_files(text_files, wav_files, SpeechHelper.generate_wav_file, ext='.txt')

    def generate_missing_files(self, expected, actual, fn, ext='.txt'):
        if len(expected) != len(actual):
            diff = set(map(extract_name, expected)) - set(map(extract_name, actual))
            for txt in diff:
                fn(txt + ext)
