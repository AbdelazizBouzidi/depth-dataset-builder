from subprocess import Popen, PIPE
from .default_wrapper import Wrapper
import json


class FFMpeg(Wrapper):
    def __init__(self, binary="ffmpeg", probe="ffprobe", quiet=False):
        super().__init__(binary, quiet)
        self.binary = binary
        self.probe = probe

    def extract_images(self, video_file, output_folder, fps=None):
        if fps is not None:
            fps_arg = ["-vf", "fps={}".format(fps)]
        else:
            fps_arg = []

        self.__call__(["-y", "-i", str(video_file), "-vsync", "0", "-qscale:v", "2"] +
                      fps_arg + [str(output_folder / output_folder.namebase + "_%05d.jpg")])
        return sorted(output_folder.files("*.jpg"))

    def extract_specific_frames(self, video_file, output_folder, frame_ids):
        '''
        Typical command string :
        ffmpeg -i in.mp4 -vf select='eq(n\\,100)+eq(n\\,184)+eq(n\\,213)' -vsync 0 frames%d.jpg
        '''
        select_string = "select='" + '+'.join(['eq(n\\,{})'.format(f) for f in frame_ids]) + "'"
        frame_string = output_folder/(video_file.namebase + "tmp_%05d.jpg")
        ffmpeg_options = ["-y", "-i", video_file,
                          "-vf", select_string, "-vsync", "0",
                          "-qscale:v", "2", frame_string]
        self.__call__(ffmpeg_options)
        frame_files = sorted(output_folder.files(video_file.namebase + "tmp_*.jpg"))
        for f, frame_id in zip(frame_files, frame_ids):
            f.rename(f.parent / (video_file.namebase + "_{:05d}.jpg".format(frame_id)))

    def get_size_and_framerate(self, video_file):
        probe_process = Popen([self.probe, "-show_entries", "stream=height,width,r_frame_rate",
                               "-of", "json", "-select_streams", "v:0", str(video_file)],
                              stdout=PIPE, stderr=PIPE)
        json_cam = json.loads(probe_process.communicate()[0])['streams'][0]
        return int(json_cam["width"]), int(json_cam["height"]), frac_to_float(json_cam["r_frame_rate"])


def frac_to_float(frac_str):
    try:
        return float(frac_str)
    except ValueError:
        num, denom = frac_str.split('/')
        return float(num) / float(denom)