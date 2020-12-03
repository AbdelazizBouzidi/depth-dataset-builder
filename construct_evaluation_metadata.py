from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from path import Path
import random
import pandas as pd
from tqdm import tqdm
import numpy as np


parser = ArgumentParser(description='Convert dataset to KITTI format, optionnally create a visualization video',
                        formatter_class=ArgumentDefaultsHelpFormatter)

parser.add_argument('--dataset_dir', metavar='DIR', type=Path, required=True,
                    help='folder containing the converted dataset')
parser.add_argument('--split', type=float, default=0,
                    help="proportion between train and test. By default, the whole dataset serves for evaluation")
parser.add_argument('--seed', type=int, default=0,
                    help='seed for random classification between train and val')
parser.add_argument('--verbose', '-v', action='count', default=0)
parser.add_argument('--max_num_samples', default=500, type=int)
parser.add_argument('--min_shift', default=0, type=int,
                    help='Minimum of former frames with valid odometry')
parser.add_argument('--allow_interpolated_frames', action='store_true',
                    help='If set, will consider frames with interpolated odometry to be valid')


def main():
    args = parser.parse_args()
    random.seed(args.seed)
    folder_tree = args.dataset_dir.walkdirs()
    video_sequences = []
    for f in folder_tree:
        if f.files('*.jpg'):
            video_sequences.append(f)

    random.shuffle(video_sequences)
    n = len(video_sequences)
    train_videos = video_sequences[:int(n*args.split)]
    test_videos = video_sequences[int(n*args.split):]

    total_valid_frames = []
    for v in tqdm(test_videos):
        metadata = pd.read_csv(v/"metadata.csv")
        valid_odometry_frames = metadata["registered"]
        if not args.allow_interpolated_frames:
            valid_odometry_frames = valid_odometry_frames & ~metadata["interpolated"]
        # Construct valid sequences
        valid_diff = valid_odometry_frames.astype(float).diff()
        invalidity_start = valid_diff.index[valid_diff == -1].tolist()
        validity_start = valid_diff.index[valid_diff == 1].tolist()
        if valid_odometry_frames.iloc[0]:
            validity_start = [0] + validity_start
        if valid_odometry_frames.iloc[-1]:
            invalidity_start.append(len(valid_odometry_frames))
        valid_sequences = [metadata.iloc[s:e].copy() for s, e in zip(validity_start, invalidity_start)]
        for s in valid_sequences:
            if len(s) <= args.min_shift:
                continue
            tvec = s[["pose03", "pose13", "pose23"]]
            displacement = np.zeros_like(tvec)
            max_shift = 3
            for j in range(1, max_shift):
                displacement += tvec.diff(j) / j
            s["fpv_x"] = s["fx"] * displacement["pose03"] / displacement["pose23"] + s["cx"]
            s["fpv_y"] = s["fy"] * displacement["pose13"] / displacement["pose23"] + s["cy"]

            valid_frames = s.iloc[args.min_shift:]
            valid_frames = valid_frames[~valid_frames["interpolated"]]

            total_valid_frames.append(valid_frames)
    total_valid_frames_df = pd.concat(total_valid_frames)
    if len(total_valid_frames_df) <= args.max_num_samples:
        final_frames = total_valid_frames_df
    else:
        final_frames = total_valid_frames_df.sample(args.max_num_samples, random_state=args.seed)
    train_dirs_list_path = args.dataset_dir / "train_folders.txt"
    image_list_path = args.dataset_dir / "test_files.txt"
    fpv_list_path = args.dataset_dir / "fpv.txt"
    with open(image_list_path, 'w') as f:
        f.writelines(line + "\n" for line in final_frames["image_path"].values)
    np.savetxt(fpv_list_path, final_frames[["fpv_x", "fpv_y"]].values)
    if len(train_videos) > 0:
        with open(train_dirs_list_path, 'w') as f:
            f.writelines([folder + "\n" for folder in train_videos])


if __name__ == '__main__':
    main()